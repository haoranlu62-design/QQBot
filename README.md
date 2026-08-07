# QQ 群 B站、抖音视频解析机器人

只有`使用文档(简略版).md`是本人写的，其他都是ai生成，还有借鉴的一个开源项目

这是一个运行在 Windows 上的 QQ 群视频解析机器人。群成员发送 B站或抖音分享链接后，机器人会解析链接并将视频或图文内容发回当前群聊。

## 功能范围

- B站普通视频链接和 `b23.tv` 短链接
- 抖音视频和图文分享链接
- 默认最长解析 480 秒的视频
- 默认单个资源上限为 90 MB

## 使用文档

- [简略启动说明](./使用文档(简略版).md)
- [完整使用文档](./使用文档.md)

## 部署说明

本仓库不包含 NapCat 运行时、QQ 登录状态、WebUI 令牌、本地环境配置、虚拟环境、缓存和日志。使用者需要自行安装 NapCat，并根据示例文件创建本地配置：

```text
qq-video-bot/.env.example       -> qq-video-bot/.env
qq-video-bot/.env.prod.example  -> qq-video-bot/.env.prod
```

`.env.prod.example` 中的本地缓存路径需要按实际安装位置修改。NapCat WebUI 登录令牌由每个使用者的 NapCat 实例自行生成，不应共享或提交到仓库。

## 开源项目与许可证

本项目使用了以下开源项目：

- [nonebot-plugin-parser](https://github.com/fllesser/nonebot-plugin-parser)：链接解析插件，原作者为 Les Freire / fllesser，采用 MIT License。本仓库包含针对当前使用场景的本地修改版，原许可证保留在 `nonebot-plugin-parser/LICENSE`。
- [NoneBot2](https://github.com/nonebot/nonebot2)：机器人应用框架。
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ)：用于连接 Windows QQ 和 OneBot V11，由使用者自行下载和安装。

本项目的修改和文档不代表上述开源项目作者对本项目提供支持、维护或背书。第三方组件分别适用其各自的许可证。本项目自编部分暂未另行声明开源许可证。

## 安全提示

- NapCat 使用非官方 QQ 接入方式，存在账号风控风险，请使用独立测试账号。
- 不要提交 WebUI Token、QQ 登录信息、B站 Cookie 或 `.env` 配置。
- 不要将 NapCat WebUI 或 OneBot WebSocket 端口暴露到公网。
- 请仅解析和传播自己有权使用的内容。
