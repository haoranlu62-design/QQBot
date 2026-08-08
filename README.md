# QQ 群视频解析机器人

这是一个运行在 Windows 上的 QQ 群机器人：群成员发送 B 站或抖音链接后，机器人会解析并把视频或图文内容发回群聊。

## 最快使用方式：下载 Release

Release 压缩包已经包含可直接使用的 `NapCat.Shell` 运行文件。不要下载 GitHub 的 `Source code (zip)`，请在仓库右侧 **Releases** 页面下载最新的 `QQBot-*.zip`。

### 1. 安装前置软件

请先安装并确认以下软件可以正常运行：

- Windows 10/11
- [QQ Windows 版](https://im.qq.com/pcqq/index.shtml)
- [Python 3.10 - 3.14](https://www.python.org/downloads/windows/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [FFmpeg](https://ffmpeg.org/download.html)，并加入系统 `PATH`

安装完成后，在 PowerShell 执行 `python --version`、`uv --version` 和 `ffmpeg -version` 检查命令是否可用。

### 2. 初始化机器人

解压到不含空格和中文的目录，例如 `D:\QQBot`。右键解压后的文件夹，在此处打开 PowerShell，执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

这个脚本会创建本地 `.env` 配置、写入正确的缓存路径，并运行一次 `uv sync --locked`。只需首次运行一次。

### 3. 启动

双击根目录的 `launch.bat`，或在 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

脚本会分别打开 NoneBot 和 NapCat 窗口。NapCat 窗口中按提示登录 QQ；建议使用专门的测试小号。首次启动后打开 [http://127.0.0.1:6099/webui](http://127.0.0.1:6099/webui)，使用 NapCat 窗口输出的 WebUI Token 登录。

### 4. 配置 NapCat 连接机器人

在 NapCat WebUI 的网络配置中新增 **WebSocket 客户端（反向 WebSocket）**：

| 配置项       | 值                                    |
| ------------ | ------------------------------------- |
| 启用         | 开                                    |
| URL          | `ws://127.0.0.1:8080/onebot/v11/ws` |
| Access Token | 留空                                  |
| 重连间隔     | `5000` 毫秒                         |

保存并重启网络配置。NoneBot 窗口出现 OneBot v11 连接成功日志后，在测试群发送 B 站或抖音链接即可。

### 5. 停止

关闭两个命令行窗口即可。需要强制关闭 QQ 时可双击 `NapCat.Shell\KillQQ.bat`。

## 从源码运行

```powershell
git clone https://github.com/haoranlu62-design/QQBot.git
cd QQBot
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

## 使用与配置

### 群内使用

在机器人所在群发送完整的 B 站或抖音分享文本，例如：

```text
https://b23.tv/xxxxxxxx
```

```text
复制打开抖音，看看这个作品 https://v.douyin.com/xxxxxxxx/
```

机器人会解析链接、下载媒体，并将作品信息和视频发送回当前群。首次测试请选择时间较短、文件较小的公开视频，并使用另一个 QQ 账号发送，不要依赖机器人账号自身触发解析。

### 只允许指定群解析

默认使用黑名单模式，允许所有群解析：

```text
PARSER_GROUP_BLACKLIST_ENABLED=true
```

如果只希望在指定群使用，将其改为 `false`，重启机器人，然后由群主、管理员或 NoneBot 超级用户在目标群发送：

```text
@机器人 开启解析
```

要关闭某个群的解析，发送：

```text
@机器人 关闭解析
```

### 常用配置

配置文件是 `qq-video-bot\.env.prod`：

| 配置项                             |        默认值 | 说明                               |
| ---------------------------------- | ------------: | ---------------------------------- |
| `HOST`                           | `127.0.0.1` | 仅允许本机访问                     |
| `PORT`                           |      `8080` | OneBot 反向 WebSocket 服务端口     |
| `PARSER_DURATION_MAXIMUM`        |       `480` | 最大视频时长，单位为秒             |
| `PARSER_MAX_SIZE`                |        `90` | 最大下载大小，单位为 MB            |
| `PARSER_APPEND_URL`              |      `true` | 回复中附加原链接                   |
| `PARSER_USE_BASE64`              |     `false` | 使用本地路径发送媒体，降低内存占用 |
| `PARSER_GROUP_BLACKLIST_ENABLED` |      `true` | 默认允许所有群解析                 |

修改 `PORT` 后，必须同步修改 NapCat WebSocket Client 的 URL。

### B 站 Cookie

不使用 Cookie 时，请删除或注释 `PARSER_BILI_CK`，不要留下空的 `PARSER_BILI_CK=`。空值可能导致旧版解析器报错。

出现 B 站错误码 `-509` 时，通常是请求频率过高或触发风控。等待一段时间后重试；确需 Cookie 时，请使用专门测试账号的完整 `name=value` Cookie，不要公开 Cookie。

### 缓存管理

视频、封面和临时文件位于 `nonebot-plugin-parser\cache`。停止机器人后可以删除旧缓存，不会破坏程序，但再次解析相同链接时需要重新下载。

检查缓存大小：

```powershell
$cache = '.\nonebot-plugin-parser\cache'
$files = Get-ChildItem -LiteralPath $cache -Recurse -File
[math]::Round((($files | Measure-Object Length -Sum).Sum / 1GB), 2)
```

### 常驻运行

电脑关机后机器人无法继续运行。需要长期使用时，请将整个项目放在持续开机的 Windows 电脑或 Windows 云服务器上，并保证 QQ、NapCat 和 NoneBot 在同一台机器运行。可以用 Windows 任务计划程序在登录后启动 `launch.bat`，同时关闭系统自动睡眠。

## 常见问题

### 浏览器访问 8080 显示 Not Found

这是正常现象。`8080` 是 OneBot WebSocket 服务，不是管理网页。NapCat 管理页面是 `http://127.0.0.1:6099/webui`。

### 群里发送链接没有反应

依次检查：

1. QQ、NapCat 和 NoneBot 是否仍在运行。
2. NoneBot 是否已经显示 `Bot ... connected`。
3. NapCat WebSocket Client 是否启用，URL 是否完全正确。
4. NapCat 与 `.env.prod` 的 Token 是否一致。
5. 链接是否由另一个 QQ 账号发送，当前群是否被白名单或黑名单规则禁用。

### 抖音可以解析，B 站失败

检查 `.env.prod` 中是否存在空的 `PARSER_BILI_CK=`，没有真实 Cookie 时应删除或注释。出现 `-509` 时等待一段时间后再试。

### 信息解析成功，但没有发送视频

可能原因包括视频超过 480 秒或 90 MB、QQ 上传超时、磁盘空间不足、FFmpeg 不可用，或站点临时限制下载。先换一个小视频测试，并查看 NoneBot 窗口最后的错误信息。

### 端口 8080 被占用

```powershell
netstat -ano | findstr :8080
```

不要同时启动两个 `bot.py`。如需修改端口，必须同时修改 `.env.prod` 的 `PORT` 和 NapCat WebSocket Client URL。

### 找不到 uv 或 FFmpeg

安装后关闭并重新打开 PowerShell，然后运行 `where.exe uv`、`uv --version` 和 `ffmpeg -version`。FFmpeg 也可使用 `winget install --id Gyan.FFmpeg` 安装。

### NapCat 找不到 QQ

请先安装 QQ Windows 版，并至少手动启动一次 QQ；仍失败时使用 `NapCat.Shell\launcher-win10-user.bat`。

## 项目结构

```text
QQBot
├─ NapCat.Shell              QQ 与 OneBot V11 接入程序
├─ nonebot-plugin-parser     链接解析插件源码和缓存目录
├─ qq-video-bot              NoneBot2 机器人主程序
├─ scripts                   初始化、启动和打包脚本
├─ launch.bat                一键启动入口
└─ README.md                 本说明
```

## 安全与隐私

NapCat 使用非官方 QQ 接入方式，请使用独立测试账号。不要把 `.env`、`.env.prod`、`NapCat.Shell\config` 或 WebUI Token 提交到 Git，也不要把 WebUI/OneBot 端口暴露到公网。项目仅应用于你有权处理和传播的内容。

## 开源组件

本项目使用 [NoneBot2](https://github.com/nonebot/nonebot2)、[nonebot-plugin-parser](https://github.com/fllesser/nonebot-plugin-parser) 和 [NapCatQQ](https://github.com/NapNeko/NapCatQQ)。第三方组件按各自许可证使用；`nonebot-plugin-parser/LICENSE` 保留了原项目许可证。
