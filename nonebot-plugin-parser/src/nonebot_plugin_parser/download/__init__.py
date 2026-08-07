import re
import asyncio
from pathlib import Path
from functools import partial
from contextlib import contextmanager
from urllib.parse import urljoin, urlsplit, parse_qsl, urlencode, urlunsplit

import httpx
import aiofiles
import curl_cffi
from nonebot import logger, get_driver
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
)
from curl_cffi.const import CurlHttpVersion

from .task import auto_task
from ..utils import merge_av, safe_unlink, generate_file_name, is_module_available
from ..config import pconfig
from ..constants import COMMON_HEADER, DOWNLOAD_TIMEOUT
from ..exception import IgnoreException, DownloadException

_DOWNLOAD_RETRY_COUNT = 5
_CURL_RETRY_COUNT = 2
_DOUYIN_CDN_LINES = (1, 2, 3, 0)
_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+)", re.IGNORECASE)
_UNSATISFIED_RANGE_RE = re.compile(r"bytes\s+\*/(\d+)", re.IGNORECASE)


class RetryableDownloadError(DownloadException):
    pass


class StreamDownloader:
    def __init__(self):
        self.headers: dict[str, str] = COMMON_HEADER.copy()
        self.cache_dir: Path = pconfig.cache_dir
        self.client: httpx.AsyncClient = httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, verify=False)

    async def aclose(self):
        await self.client.aclose()

    @staticmethod
    @contextmanager
    def rich_progress(
        desc: str,
        total: int | None = None,
        completed: int = 0,
    ):
        with Progress(
            TextColumn("[bold blue]{task.description}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "|",
            DownloadColumn(),
        ) as progress:
            task_id = progress.add_task(description=desc, total=total, completed=completed)
            yield partial(progress.update, task_id)

    @staticmethod
    def _partial_path(file_path: Path) -> Path:
        return file_path.with_name(f"{file_path.name}.part")

    @staticmethod
    def _download_url_for_attempt(url: str, attempt: int) -> str:
        """Rotate Douyin CDN lines while leaving other platform URLs unchanged."""
        parts = urlsplit(url)
        if parts.hostname != "aweme.snssdk.com":
            return url

        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["line"] = str(_DOUYIN_CDN_LINES[(attempt - 1) % len(_DOUYIN_CDN_LINES)])
        return urlunsplit(parts._replace(query=urlencode(query)))

    @staticmethod
    def _should_request_range(url: str, resume_offset: int) -> bool:
        return resume_offset > 0 or urlsplit(url).hostname == "aweme.snssdk.com"

    @staticmethod
    def _validate_total_size(total_size: int, url: object) -> int:
        if total_size <= 0:
            logger.warning(f"媒体 url: {url}, 大小为 0, 取消下载")
            raise IgnoreException

        file_size = total_size / 1024 / 1024
        if file_size > pconfig.max_size:
            logger.warning(f"媒体 url: {url} 大小 {file_size:.2f} MB, 超过 {pconfig.max_size} MB, 取消下载")
            raise IgnoreException

        return total_size

    @staticmethod
    def _validate_content_length(
        response: httpx.Response | curl_cffi.Response,
    ) -> int:
        """获取文件长度"""
        content_length = response.headers.get("Content-Length")
        content_length = int(content_length) if content_length else 0

        return StreamDownloader._validate_total_size(content_length, response.url)

    @classmethod
    def _download_plan(
        cls,
        response: httpx.Response | curl_cffi.Response,
        resume_offset: int,
    ) -> tuple[int, str, int]:
        """Return total size, file mode, and initial progress for a response."""
        if response.status_code == 206:
            content_range = response.headers.get("Content-Range", "")
            matched = _CONTENT_RANGE_RE.fullmatch(content_range.strip())
            if not matched:
                raise RetryableDownloadError(f"Invalid Content-Range: {content_range!r}")

            start, end, total_size = (int(value) for value in matched.groups())
            if start != resume_offset or end < start or end >= total_size:
                raise RetryableDownloadError(f"Unexpected Content-Range {content_range!r} for offset {resume_offset}")

            cls._validate_total_size(total_size, response.url)
            return total_size, "ab", resume_offset

        total_size = cls._validate_content_length(response)
        return total_size, "wb", 0

    @staticmethod
    async def _replace_with_retry(source: Path, destination: Path) -> Path:
        for attempt in range(5):
            try:
                source.replace(destination)
                return destination
            except PermissionError:
                if attempt == 4:
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))

        raise RuntimeError("Unreachable")

    @classmethod
    async def _complete_partial_download(
        cls,
        part_path: Path,
        file_path: Path,
        total_size: int,
    ) -> Path:
        actual_size = part_path.stat().st_size if part_path.exists() else 0
        if actual_size != total_size:
            raise RetryableDownloadError(f"Incomplete download: received {actual_size} bytes, expected {total_size}")

        return await cls._replace_with_retry(part_path, file_path)

    @classmethod
    async def _finish_satisfied_range(
        cls,
        response: httpx.Response | curl_cffi.Response,
        part_path: Path,
        file_path: Path,
        resume_offset: int,
    ) -> Path | None:
        if response.status_code != 416:
            return None

        content_range = response.headers.get("Content-Range", "")
        matched = _UNSATISFIED_RANGE_RE.fullmatch(content_range.strip())
        if matched and int(matched.group(1)) == resume_offset:
            return await cls._replace_with_retry(part_path, file_path)

        part_path.unlink(missing_ok=True)
        raise RetryableDownloadError(f"Server rejected resume offset {resume_offset}: {content_range!r}")

    async def _download_file_with_httpx(
        self,
        url: str,
        *,
        file_path: Path,
        headers: dict[str, str],
        chunk_size: int = 64 * 1024,
    ) -> Path:
        """download file by url with stream"""
        part_path = self._partial_path(file_path)
        resume_offset = part_path.stat().st_size if part_path.exists() else 0
        request_headers = headers.copy()
        if self._should_request_range(url, resume_offset):
            request_headers["Range"] = f"bytes={resume_offset}-"

        async with self.client.stream(
            "GET",
            url,
            headers=request_headers,
            follow_redirects=True,
        ) as response:
            if completed_path := await self._finish_satisfied_range(response, part_path, file_path, resume_offset):
                return completed_path

            response.raise_for_status()
            total_size, file_mode, completed = self._download_plan(response, resume_offset)

            with self.rich_progress(
                f"httpx | {file_path.name}",
                total_size,
                completed,
            ) as update_progress:
                async with aiofiles.open(part_path, file_mode) as file:
                    async for chunk in response.aiter_bytes(chunk_size):
                        await file.write(chunk)
                        update_progress(advance=len(chunk))

        return await self._complete_partial_download(part_path, file_path, total_size)

    async def _download_file_with_curl_cffi(
        self,
        url: str,
        *,
        file_path: Path,
        headers: dict[str, str],
    ) -> Path:
        part_path = self._partial_path(file_path)
        resume_offset = part_path.stat().st_size if part_path.exists() else 0
        request_headers = headers.copy()
        if self._should_request_range(url, resume_offset):
            request_headers["Range"] = f"bytes={resume_offset}-"

        async with curl_cffi.AsyncSession(
            allow_redirects=True,
            http_version=CurlHttpVersion.V1_1,
        ) as session:
            response: curl_cffi.Response = await session.get(
                url,
                headers=request_headers,
                timeout=DOWNLOAD_TIMEOUT,
                stream=True,
            )
            if completed_path := await self._finish_satisfied_range(response, part_path, file_path, resume_offset):
                return completed_path

            response.raise_for_status()
            total_size, file_mode, completed = self._download_plan(response, resume_offset)

            with self.rich_progress(
                f"curl_cffi | {file_path.name}",
                total_size,
                completed,
            ) as update_progress:
                async with aiofiles.open(part_path, file_mode) as file:
                    async for chunk in response.aiter_content(chunk_size=8192):
                        await file.write(chunk)
                        update_progress(advance=len(chunk))

        return await self._complete_partial_download(part_path, file_path, total_size)

    async def _download_file(
        self,
        url: str,
        *,
        file_name: str | None = None,
        ext_headers: dict[str, str] | None = None,
        chunk_size: int = 64 * 1024,
    ) -> Path:
        """download file by url with fallback"""
        if not file_name:
            file_name = generate_file_name(url)
        file_path = self.cache_dir / file_name
        if file_path.exists():
            return file_path

        headers = {**self.headers, **(ext_headers or {})}

        for attempt in range(1, _DOWNLOAD_RETRY_COUNT + 1):
            try:
                attempt_url = self._download_url_for_attempt(url, attempt)
                return await self._download_file_with_httpx(
                    attempt_url,
                    file_path=file_path,
                    headers=headers,
                    chunk_size=chunk_size,
                )
            except IgnoreException:
                raise
            except (httpx.HTTPError, RetryableDownloadError) as exc:
                part_path = self._partial_path(file_path)
                part_size = part_path.stat().st_size if part_path.exists() else 0
                logger.warning(f"下载中断 (httpx {attempt}/{_DOWNLOAD_RETRY_COUNT})，将从 {part_size} 字节续传: {exc}")
                if attempt < _DOWNLOAD_RETRY_COUNT:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))

        for attempt in range(1, _CURL_RETRY_COUNT + 1):
            try:
                attempt_url = self._download_url_for_attempt(url, attempt)
                return await self._download_file_with_curl_cffi(
                    attempt_url,
                    file_path=file_path,
                    headers=headers,
                )
            except IgnoreException:
                raise
            except (curl_cffi.CurlError, RetryableDownloadError) as exc:
                part_path = self._partial_path(file_path)
                part_size = part_path.stat().st_size if part_path.exists() else 0
                logger.warning(f"下载中断 (curl_cffi {attempt}/{_CURL_RETRY_COUNT})，将从 {part_size} 字节续传: {exc}")
                if attempt < _CURL_RETRY_COUNT:
                    await asyncio.sleep(2)

        raise DownloadException("媒体下载重试后仍然失败")

    @auto_task
    async def download_video(
        self,
        url: str,
        *,
        video_name: str | None = None,
        ext_headers: dict[str, str] | None = None,
    ) -> Path:
        """download video file by url with stream"""
        if video_name is None:
            video_name = generate_file_name(url, ".mp4")

        return await self._download_file(
            url,
            file_name=video_name,
            ext_headers=ext_headers,
            chunk_size=1024 * 1024,
        )

    @auto_task
    async def download_audio(
        self,
        url: str,
        *,
        audio_name: str | None = None,
        ext_headers: dict[str, str] | None = None,
    ) -> Path:
        """download audio file by url with stream"""
        if audio_name is None:
            audio_name = generate_file_name(url, ".mp3")

        return await self._download_file(
            url,
            file_name=audio_name,
            ext_headers=ext_headers,
        )

    @auto_task
    async def download_img(
        self,
        url: str,
        *,
        img_name: str | None = None,
        ext_headers: dict[str, str] | None = None,
    ) -> Path:
        """download image file by url with stream"""
        if img_name is None:
            img_name = generate_file_name(url, ".jpg")

        return await self._download_file(
            url,
            file_name=img_name,
            ext_headers=ext_headers,
        )

    @auto_task
    async def download_av_and_merge(
        self,
        v_url: str,
        a_url: str,
        *,
        output_path: Path,
        ext_headers: dict[str, str] | None = None,
    ) -> Path:
        """download video and audio file by url with stream and merge"""
        v_path, a_path = await asyncio.gather(
            self._download_file(v_url, ext_headers=ext_headers),
            self._download_file(a_url, ext_headers=ext_headers),
        )
        await merge_av(v_path=v_path, a_path=a_path, output_path=output_path)
        return output_path

    @auto_task
    async def download_m3u8(
        self,
        m3u8_url: str,
        *,
        video_name: str | None = None,
        ext_headers: dict[str, str] | None = None,
    ) -> Path:
        """download m3u8 file by url with stream"""
        if video_name is None:
            video_name = generate_file_name(m3u8_url, ".mp4")

        video_path = pconfig.cache_dir / video_name

        try:
            async with aiofiles.open(video_path, "wb") as f:
                total_size = 0
                with self.rich_progress(desc=video_name) as update_progress:
                    for url in await self._get_m3u8_slices(m3u8_url):
                        async with self.client.stream("GET", url, headers=ext_headers) as response:
                            async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                                await f.write(chunk)
                                total_size += len(chunk)
                                update_progress(advance=len(chunk), total=total_size)
        except httpx.HTTPError:
            await safe_unlink(video_path)
            logger.exception("m3u8 视频下载失败")
            raise DownloadException("m3u8 视频下载失败")

        return video_path

    async def _get_m3u8_slices(self, m3u8_url: str):
        """获取 m3u8 分片"""

        response = await self.client.get(m3u8_url)
        response.raise_for_status()

        slices_text = response.text
        slices: list[str] = []

        for line in slices_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            slices.append(urljoin(m3u8_url, line))

        return slices


downloader: StreamDownloader = StreamDownloader()
"""全局下载器实例，提供下载功能"""
yt_dlp_downloader = None
"""yt-dlp 下载器实例，提供下载视频功能，若 yt-dlp 未安装则为 None"""

if is_module_available("yt_dlp"):
    from .ytdlp import YtdlpDownloader

    yt_dlp_downloader = YtdlpDownloader()


@get_driver().on_shutdown
async def close_download_client():
    logger.debug("正在关闭下载器...")
    await downloader.aclose()
