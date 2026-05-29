# AstrBot Phi Plugin Query Core

AstrBot 原生 Phigros 查询核心插件，基于 `phi-plugin` 的资源与算法分阶段重构。

## 当前支持

- `phi help`：查看帮助与迁移状态
- `phi song <曲名或别名>`：查询曲目信息
- `phi search <关键词>`：搜索曲目
- `phi rand`：随机曲目
- `phi ill <曲名或别名>`：发送本地曲绘（存在时）
- `phi bind <sessionToken|查询ID>`：绑定 token，并尝试登录查询 API 获取 internal_id；也可直接绑定查询 ID
- `phi cnbind <sessionToken>` / `phi gbbind <sessionToken>`：按国服/国际服入口绑定 token
- `phi auth <API Token>` / `phi login <API Token>`：通过查询平台 API Token 换取并保存 sessionToken
- `phi unbind`：解绑并清理缓存
- `phi clean`：清理当前用户插件数据
- `phi update`：尝试从查询 API 拉取并缓存标准化存档
- `phi b30` / `phi rks`：基于缓存存档输出 B30/RKS 摘要
- `phi pgr` / 顶层 `pgr`：同样查询 B30/RKS
- `phi score <曲名或别名>`：查询单曲成绩
- `phi info`：查询用户统计摘要
- `phi data`：查询 Data 数量（存档包含 `gameProgress.money` 时）
- `phi id`：查看已绑定查询 ID 和缓存存档中的 PlayerId
- `phi sessiontoken`：查看本地 token 脱敏信息

命令触发使用 AstrBot 原生 `@filter.command("phi")`，实际前缀由 AstrBot 全局唤醒/命令配置处理，本插件不再自行监听 `#` 或 `/`。

命令运行逻辑拆分在 `phi_core/commands/` 下：每个原插件函数级命令对应一个独立脚本，路由器会自动发现带有 `ALIASES` 和 `handle` 的命令模块。暂未迁移完整业务逻辑的命令也保留独立脚本并返回清晰提示，方便后续逐个补齐。

图片渲染默认优先使用 AstrBot 官方 `Star.html_render`，通过 `HTML + Jinja2` 模板走 AstrBot 内置截图服务，尽量贴近原版 phi-plugin 的 Puppeteer 模板截图流程；如果官方 HTML 渲染不可用，会自动回退到内置 Pillow 面板。渲染器会复用原版插件的本地字体思路，使用 `resources/fonts/` 中的 Noto/Aldrich 字体绘制中文和英文，并会把当前面板需要的字符裁剪成小字体 data URI，避免远端 T2I 服务读取不到本机字体导致中文渲染失败。生成文件写入 AstrBot 插件数据目录下的 `cache/render/`，字体子集缓存写入 `cache/fonts/`；如需纯文本输出，可在配置中将 `render_mode` 改为 `text`。

## 迁移说明

插件侧不依赖 Node.js、Yunzai、Redis 或自管 Puppeteer；HTML 图片模板交给 AstrBot 官方 `html_render` 渲染。小游戏、排行榜、评论、标签、签到任务、管理命令和插件自更新暂未迁移。

运行期数据、绑定、缓存和后续下载数据均写入 `StarTools.get_data_dir("astrbot_plugin_phi_plugin")` 对应的 AstrBot 插件数据目录；插件包内 `resources/` 只存放随插件发布的静态曲库资源。

如果 `phi update` 所连接的服务没有返回标准化存档 JSON，插件会给出安全提示；后续可以在 `phi_core/save/client.py` 与 `phi_core/save/codec.py` 中继续补齐云存档协议。

`phi bind <sessionToken>` 会先本地保存 token，再尝试调用查询 API `/bind` 获取 internal_id。若 API 暂时不可用，token 绑定仍可保留；`phi bind <查询ID>` 则会按 API ID 方式绑定并清理旧 token，避免凭据冲突。已经保存 token 时，直接运行 `phi bind` 会尝试重新登录查询 API 并补齐查询 ID。TapTap 二维码扫码登录仍在迁移中，当前会返回明确提示。

`phi auth <API Token>` 对齐原插件 `auth` 流程，会调用 `/getPgrToken` 获取用户 sessionToken 并保存到 AstrBot 插件数据目录。为降低泄露风险，AstrBot 版不会在聊天中明文输出完整 sessionToken；需要确认本地状态时可使用 `phi sessiontoken` 查看脱敏信息。

## 本地验证

```powershell
python -m compileall .
python scripts\smoke_command_routes.py
python scripts\smoke_dispatch.py
```
