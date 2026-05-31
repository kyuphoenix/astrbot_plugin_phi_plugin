# AstrBot Phi Plugin Query Core

AstrBot 原生 Phigros 查询核心插件，基于 `phi-plugin` 的资源与算法分阶段重构。

## 当前支持

- `phi help`：查看帮助与迁移状态
- `phi song <曲名或别名>`：查询曲目信息
- `phi search <关键词>`：搜索曲目
- `phi rand`：随机曲目
- `phi ill <曲名或别名>`：发送本地曲绘（存在时）
- `phi down ill` / `phi 下载曲绘`：下载或更新原版曲绘到 AstrBot 数据目录
- `phi bind <sessionToken|查询ID|qrcode>`：绑定 token、查询 ID 或 TapTap 二维码登录，并在绑定后自动同步一次玩家数据
- `phi cnbind <sessionToken>` / `phi gbbind <sessionToken>`：按国服/国际服入口绑定 token
- `phi auth <API Token>` / `phi login <API Token>`：通过查询平台 API Token 换取并保存 sessionToken，随后自动同步一次玩家数据
- `phi unbind`：解绑并清理缓存
- `phi clean`：清理当前用户插件数据
- `phi update`：尝试从查询 API 拉取标准化存档，并展示本地历史对比得到的进步摘要
- `phi b30` / `phi rks`：基于缓存存档输出 B30/RKS 摘要
- `phi pgr` / 顶层 `pgr`：同样查询 B30/RKS
- `phi score <曲名或别名>`：查询单曲成绩
- `phi info`：查询用户统计摘要
- `phi data`：查询 Data 数量（存档包含 `gameProgress.money` 时）
- `phi id`：查看已绑定查询 ID 和缓存存档中的 PlayerId
- `phi sessiontoken`：查看本地 token 脱敏信息
- `phi tips`：从本地 `tips.yaml` 随机抽取一条 Tips
- `phi alias <曲名或别名>`：查询本地曲目别名
- `phi com <定数> <acc>` / `phi 计算 <定数> <acc>`：计算等效 RKS
- `phi table <定数>` / `phi 定数表 <定数>`：查询当前曲库定数表
- `phi newlog [版本号]`：查看本地曲库更新日志
- `phi newnotice`：查看本地公告
- `phi best [数量]`：文本版 Best 列表
- `phi p30` / `phi fc30` / `phi x30`：AP、FC、1 Good 模式成绩列表
- `phi lmtacc <acc>`：限制最低 ACC 后查看 Best 列表
- `phi list [条件]`：按定数、ACC、难度、评级筛选成绩，例如 `phi list 14-15 IN -acc 98+ FC`
- `phi lvscore [条件]`：统计指定范围成绩，例如 `phi lvscore 13-15 IN AT`
- `phi suggest` / `phi 推分建议`：基于缓存成绩估算推分建议
- `phi randclg [范围]`：随机三曲课题，例如 `phi randclg 30-45`

命令触发使用 AstrBot 原生 `@filter.command_group("phi")`，实际前缀由 AstrBot 全局唤醒/命令配置处理，本插件不再自行监听 `#` 或 `/`。

命令运行逻辑拆分在 `phi_core/commands/` 下：每个原插件函数级命令对应一个独立脚本，路由器会自动发现带有 `ALIASES` 和 `handle` 的命令模块。暂未迁移完整业务逻辑的命令也保留独立脚本并返回清晰提示，方便后续逐个补齐。

图片渲染使用 AstrBot 官方 `Star.html_render`，并优先复用原版 `resources/html/` 下的 CSS、字体与图片资源。`phi help`、`phi b30/rks/pgr` 已接入原版 `help`/`b19` 资源结构；其它纯文本结果暂时仍使用通用 HTML 面板。Pillow 面板回退已移除，方便暴露真实 HTML 渲染问题。生成文件写入 AstrBot 插件数据目录下的 `cache/render/`；如需纯文本输出，可在配置中将 `render_mode` 改为 `text`。

## 迁移说明

插件侧不依赖 Node.js、Yunzai、Redis 或自管 Puppeteer；HTML 图片模板交给 AstrBot 官方 `html_render` 渲染。小游戏、排行榜、签到任务、管理命令和插件自更新暂未迁移。

运行期数据、绑定、缓存和后续下载数据均写入 `StarTools.get_data_dir("astrbot_plugin_phi_plugin")` 对应的 AstrBot 插件数据目录。插件不再随包携带 `resources/`；首次启动或执行 `phi down resources` 时，会把 Jinja2 HTML 模板仓库 `kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template` 拉取到 `downloads/html`，并继续从原版 `Catrong/phi-plugin` 拉取 `downloads/info` 与 `downloads/otherill`。渲染模板、曲库、帮助、头像、字体等资源都从这里读取。

曲绘下载命令会把 `https://github.com/Catrong/phi-plugin-ill.git` 克隆或更新到 AstrBot 数据目录下的 `downloads/original_ill/`，渲染和 `phi ill` 会优先读取这里的曲绘资源。`phi down all` 会同时更新 Jinja2 HTML 模板、原版 info/otherill 与曲绘。若配置了 `github_proxy`，下载命令会沿用该代理前缀。

如果 `phi bind` 或 `phi update` 所连接的服务没有返回标准化存档 JSON，插件会给出安全提示；后续可以在 `phi_core/save/client.py` 与 `phi_core/save/codec.py` 中继续补齐云存档协议。

`phi bind <sessionToken>` 会先本地保存 token，再尝试调用查询 API `/bind` 获取 internal_id，并立即拉取一次存档写入 AstrBot 数据目录。若绑定 API 暂时不可用，token 绑定仍可保留，插件会继续尝试用 token 同步存档；`phi bind <查询ID>` 则会按 API ID 方式绑定并清理旧 token，避免凭据冲突。已经保存 token 时，直接运行 `phi bind` 会尝试重新登录查询 API、补齐查询 ID 并刷新存档缓存。TapTap 二维码登录使用 `phi bind qrcode`。

`phi auth <API Token>` 对齐原插件 `auth` 流程，会调用 `/getPgrToken` 获取用户 sessionToken 并保存到 AstrBot 插件数据目录，随后自动同步一次存档，因此通常可以直接运行 `phi pgr`。为降低泄露风险，AstrBot 版不会在聊天中明文输出完整 sessionToken；需要确认本地状态时可使用 `phi sessiontoken` 查看脱敏信息。

`phi update` 会保留“拉取并缓存最新存档”的副作用，但面向用户展示的是进步情况：RKS / Data / 课题分变化、当前存档时间记录到的成绩数，以及按日期聚合的近期成绩变化。插件会优先合并查询平台返回的历史记录，接口不可用时回退到本地历史。本地历史记录写入 AstrBot 数据目录下的 `history/`，解绑或换绑账号时会随缓存一起清理，避免不同账号的进步记录串档。

## 本地验证

```powershell
python -m compileall .
python scripts\smoke_command_routes.py
python scripts\smoke_command_group.py
python scripts\smoke_dispatch.py
python scripts\smoke_send_components.py
```
