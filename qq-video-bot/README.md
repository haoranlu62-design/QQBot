# QQ Video Bot

This is a minimal NoneBot2 application for parsing Bilibili and Douyin links
in QQ groups through NapCat and OneBot v11.

## 1. Install

```powershell
cd D:\123\ai\QQbot\BOT2\qq-video-bot
uv sync
```

FFmpeg must be available on `PATH`. The current machine already has it.

## 2. Start NoneBot

```powershell
uv run python bot.py
```

The bot listens on `127.0.0.1:8080`. Keep this terminal open.

Runtime settings are stored in `.env.prod`; `.env` selects that environment.
Parser downloads are cached in
`D:\123\ai\QQbot\BOT2\nonebot-plugin-parser\cache`.

## 3. Configure NapCat

In NapCat WebUI, add a WebSocket client (reverse WebSocket) with:

- Enable: on
- URL: `ws://127.0.0.1:8080/onebot/v11/ws`
- Access token: empty for the initial local test
- Reconnect interval: `5000` ms

Save and restart the network configuration. The NoneBot terminal should then
report that a OneBot v11 bot connected.

## 4. Test In QQ

Paste each of these message types directly into a test group:

- A `https://www.bilibili.com/video/BV...` link
- A `https://b23.tv/...` link
- A complete Douyin share message containing `https://v.douyin.com/...`
- A Douyin image-post link

The first test should use a small public video. By default, videos longer than
480 seconds or larger than 90 MB are rejected.

Leave `PARSER_BILI_CK` undefined unless it contains a real Bilibili cookie in
`name=value;name=value` format. An empty value is not a valid cookie.

## Security

NapCat uses an unofficial QQ client protocol. Use a dedicated test account,
keep NapCat and NoneBot bound to localhost, and do not expose either WebUI or
OneBot endpoint to the public Internet.
