from pathlib import Path

import httpx
import pytest
from nonebot import logger


def test_generate_file_name():
    import random

    from nonebot_plugin_parser.utils import generate_file_name

    suffix_lst = [
        ".jpg",
        ".png",
        ".gif",
        ".webp",
        ".jpeg",
        ".bmp",
        ".tiff",
        ".ico",
        ".svg",
        ".heic",
        ".heif",
    ]
    # 测试 100 个链接
    for i in range(20):
        url = f"https://www.google.com/test{i}{random.choice(suffix_lst)}"
        file_name = generate_file_name(url)
        new_file_name = generate_file_name(url)
        assert file_name == new_file_name
        logger.info(f"{url}: {file_name}")


def test_limited_size_dict():
    from nonebot_plugin_parser.download.ytdlp import LimitedSizeDict

    limited_size_dict = LimitedSizeDict()
    for i in range(20):
        limited_size_dict[f"test{i}"] = f"test{i}"
    assert len(limited_size_dict) == 20
    for i in range(20):
        assert limited_size_dict[f"test{i}"] == f"test{i}"
    for i in range(20, 30):
        limited_size_dict[f"test{i}"] = f"test{i}"
    assert len(limited_size_dict) == 20


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"abcd"
        raise httpx.RemoteProtocolError("connection closed during response body")


async def _build_downloader(tmp_path: Path, handler):
    from nonebot_plugin_parser.download import StreamDownloader

    downloader = StreamDownloader()
    await downloader.client.aclose()
    downloader.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    downloader.cache_dir = tmp_path
    return downloader


async def test_download_resumes_after_connection_break(tmp_path: Path, monkeypatch):
    import nonebot_plugin_parser.download as download_module

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            assert "Range" not in request.headers
            return httpx.Response(
                200,
                headers={"Content-Length": "10"},
                stream=BrokenStream(),
            )

        assert request.headers["Range"] == "bytes=4-"
        return httpx.Response(
            206,
            headers={
                "Content-Length": "6",
                "Content-Range": "bytes 4-9/10",
            },
            content=b"efghij",
        )

    async def no_sleep(_: float):
        pass

    monkeypatch.setattr(download_module.asyncio, "sleep", no_sleep)
    downloader = await _build_downloader(tmp_path, handler)
    try:
        path = await downloader._download_file(
            "https://example.com/video",
            file_name="video.mp4",
            chunk_size=4,
        )
    finally:
        await downloader.aclose()

    assert len(requests) == 2
    assert path.read_bytes() == b"abcdefghij"
    assert not (tmp_path / "video.mp4.part").exists()


async def test_download_restarts_when_server_ignores_range(tmp_path: Path):
    part_path = tmp_path / "video.mp4.part"
    part_path.write_bytes(b"stale")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Range"] == "bytes=5-"
        return httpx.Response(
            200,
            headers={"Content-Length": "5"},
            content=b"fresh",
        )

    downloader = await _build_downloader(tmp_path, handler)
    try:
        path = await downloader._download_file("https://example.com/video", file_name="video.mp4")
    finally:
        await downloader.aclose()

    assert path.read_bytes() == b"fresh"
    assert not part_path.exists()


@pytest.mark.parametrize(
    ("attempt", "line"),
    [(1, "1"), (2, "2"), (3, "3"), (4, "0"), (5, "1")],
)
def test_douyin_download_rotates_cdn_lines(attempt: int, line: str):
    from urllib.parse import parse_qs, urlsplit

    from nonebot_plugin_parser.download import StreamDownloader

    original_url = "https://aweme.snssdk.com/aweme/v1/play/?video_id=test&ratio=720p&line=0"
    attempt_url = StreamDownloader._download_url_for_attempt(original_url, attempt)

    assert parse_qs(urlsplit(attempt_url).query)["line"] == [line]
