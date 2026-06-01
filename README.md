# AstrBot Phi Plugin

AstrBot 原生 Phigros 查询插件，基于 [Catrong/phi-plugin](https://github.com/Catrong/phi-plugin) 的资源、算法和 HTML 模板进行迁移。当前版本不再依赖 Yunzai、Node.js、Redis 或自管 Puppeteer，命令注册、数据目录、HTML 转图片和配置面板均走 AstrBot 原生能力。

## 功能概览

- 使用 AstrBot 原生 `@filter.command_group("phi")` 注册命令，实际命令前缀由 AstrBot 全局配置决定，不再内置监听 `#` 或 `/`。
- 运行期数据写入 `StarTools.get_data_dir("astrbot_plugin_phi_plugin")` 对应的 AstrBot 插件数据目录，绑定、缓存、历史记录、下载资源均不写入插件源码目录。
- 首次启动或执行资源下载命令时，会自动拉取 Jinja2 HTML 模板、原版 `info` / `otherill` 资源以及曲绘仓库。
- 图片渲染使用 AstrBot 官方 `Star.html_render` / T2I 服务，并逐步迁移原版 `.art + css` 模板到 Jinja2 模板链路。
- 支持远程曲绘模式和本地曲绘模式：远程模式向 T2I 传入 GitHub 曲绘 URL，本地模式读取已下载曲绘并转为 base64。
- 图片发送采用原图、JPG、WebP 三级 fallback，降低平台富媒体发送失败概率。
- 同一用户命令已加异步队列锁，避免同一用户连续发送命令时并发读写存档、Notes 或小游戏状态。
- `phi guess` / `phi tipgame` / `phi ltr` 小游戏支持原命令唤醒方式，也可通过配置开启普通消息直接回复监听。

## 已支持命令

下表以原版 `phi-plugin` README 的功能描述为基础，并补充当前 AstrBot 迁移版已经实现的差异。命令示例均使用 `phi` 命令组；顶层 `pgr` 也可直接触发 B30/RKS 面板。

| 命令 | 别名/示例 | 当前实现与说明 |
| --- | --- | --- |
| `phi help` | `phi 帮助` / `phi 菜单` / `phi 命令` / `phi 指令` | 查看 Phi-Plugin 帮助菜单，使用原版帮助资源与随机曲绘背景渲染。 |
| `pgr` | `屁股肉` | 顶层快捷命令，快速查看当前绑定玩家的 B30/RKS 成绩面板。 |
| `phi pgr` | `phi 屁股肉` | 查看当前绑定玩家的 B30/RKS 成绩面板，复用原版 B19/B30 模板链路。 |
| `phi b30` | `phi b1` 到 `phi b100` | 查看 Best 30/Best N 成绩与 RKS 面板，动态数量命令会路由到同一套 B30 逻辑。 |
| `phi rks` |  | 查询玩家当前 RKS 信息，使用 B30/RKS 查询链路。 |
| `phi best` | `phi best 50` | 生成文字版 B30/Best N 成绩列表，不走 T2I。 |
| `phi p30` | `phi p1` 到 `phi p100` | 查看 All Perfect 模式下的 Top N 成绩，图片模式使用 B30 同款模板。 |
| `phi fc30` | `phi fc1` 到 `phi fc100` | 查看 Full Combo 模式下的 Top N 成绩，图片模式使用 B30 同款模板。 |
| `phi x30` | `phi x1` 到 `phi x100` | 查看 1 Good 模式下的 Top N 成绩，图片模式使用 B30 同款模板。 |
| `phi arcgros` | `phi arcgrosb19` / `phi arcgrosb30` 等 | 以 Arcgros 风格查看 B19/B30 等成绩面板，支持 `arcgrosbN` 自定义数量。 |
| `phi update` | `phi 更新存档` | 同步存档并查看最近进步情况；会合并远端历史与本地历史，展示 RKS/Data/课题分变化、近期成绩变化和今日任务。 |
| `phi info` |  | 查看玩家信息总览面板，迁移原版 userinfo 信息卡与历史曲线数据。 |
| `phi info1` |  | 查看玩家信息面板第一页。 |
| `phi info2` |  | 查看玩家信息面板第二页。 |
| `phi data` |  | 查看当前存档的 Data 数量与进度信息。 |
| `phi score` | `phi 单曲成绩 <曲名>` | 查询指定曲目的单曲成绩，支持排序/筛选参数并可展示推分建议。 |
| `phi list` | 示例：`phi list 14-15 IN -acc 98+ FC` | 按定数、ACC、难度、评级等条件筛选并列出成绩，结果过多时提示缩小筛选范围。 |
| `phi lvscore` | `phi lvsco` / `phi scolv` | 查看指定等级范围内的成绩统计。 |
| `phi lmtacc` | `phi lmtacc 98` | 按 ACC 下限筛选成绩并计算 RKS。 |
| `phi suggest` | `phi 推分` / `phi 推分建议` | 根据当前成绩生成推分建议，帮助估算 RKS 提升目标。 |
| `phi hisb30` |  | 根据历史记录查看 B30 变化，使用原版 historyB30 模板链路。 |
| `phi achievement` | `phi ahv` | 查看玩家成就统计与完成情况。 |
| `phi 2025history` | `phi 年度总结` | 查看 2025 年度总结。 |
| `phi bind` | `phi 绑定 <sessionToken\|查询ID\|qrcode>` | 绑定 sessionToken、查询 ID 或 TapTap 二维码登录；绑定成功后会自动同步一次玩家数据。 |
| `phi cnbind` | `phi cn绑定` | 按国服方式绑定账号或查询 ID。 |
| `phi gbbind` | `phi gb绑定` | 按国际服方式绑定账号或查询 ID。 |
| `phi auth` | `phi login <API Token>` / `phi 登录 <API Token>` | 使用查分平台 API Token 换取 sessionToken 并绑定账号，随后自动同步一次存档。 |
| `phi unbind` | `phi 解绑` | 解绑账号并清理当前用户缓存。 |
| `phi clean` |  | 清理当前用户的绑定、本地存档和历史缓存数据。 |
| `phi id` | `phi apiid` / `phi uid` / `phi 查询id` | 查看当前绑定的查询 ID、PlayerId 与玩家名。 |
| `phi sessiontoken` | `phi tk` / `phi token` | 查看本地 sessionToken 绑定状态与帮助，聊天中只展示脱敏信息。 |
| `phi setapitoken` |  | 设置查分平台 API Token。 |
| `phi tokenlist` | `phi tkls` / `phi lstk` | 查看查分平台 Token 列表。 |
| `phi api` | `phi api help` | 查看 Phi 查分平台 API 相关帮助。 |
| `phi song` | `phi 曲 <曲名>` | 查询曲目基础信息与图鉴信息，支持本地别名检索。 |
| `phi chart` | `phi chart <曲名> [EZ/HD/IN/AT]` | 查询指定曲目的谱面信息与标签。 |
| `phi ill` | `phi 曲绘 <曲名>` | 查看指定曲目的曲绘；远程模式实时拉取 GitHub 曲绘，本地模式读取已下载文件。 |
| `phi search` | `phi 查找` / `phi 检索` | 搜索曲目，支持按曲名、别名等信息检索。 |
| `phi alias` | `phi alias <曲名>` | 查询、添加或管理曲目别名。 |
| `phi setnick` | `phi 设置别名` / `phi setnic` | 为曲目设置自定义别名。 |
| `phi delnick` | `phi 删除别名` / `phi delnic` | 删除已设置的曲目别名。 |
| `phi table` | `phi 定数表 <定数>` | 查询当前曲库定数表。 |
| `phi rand` | `phi random` / `phi 随机` | 按条件随机抽取一首曲目或谱面，支持定数与难度范围。 |
| `phi randclg` | 示例：`phi randclg 30-45` | 生成随机课题组，图片模式使用迁移后的随机课题模板。 |
| `phi chap` | `phi chap help` | 按章节查询曲目列表与章节成绩统计。 |
| `phi tag` |  | 查询谱面标签统计。 |
| `phi settag` |  | 为谱面设置或投票标签。 |
| `phi addtag` | `phi retag` / `phi subtag` | 为谱面添加或提交标签。 |
| `phi comment` | `phi cmt` / `phi 评论` / `phi 评价` | 查看或发布曲目在线评论。 |
| `phi recmt` | `phi recmt <评论ID>` | 删除自己发布的在线评论。 |
| `phi mycmt` |  | 查看自己发布的在线评论。 |
| `phi ranklist` | `phi 排行榜 [名次]` | 查看 RKS 排行榜或自己的排名。 |
| `phi rankfind` | `phi 查询排名 <rks>` | 按 RKS 查询大致排行榜位置。 |
| `phi newlog` | `phi newlog [版本号]` | 查看 Phigros 最新版本更新日志，会尝试拉取 TapTap 更新文本并使用原版 newSong 模板渲染。 |
| `phi newnotice` |  | 查看 Phigros 最新公告。 |
| `phi tips` |  | 随机查看一条 Phigros 小提示。 |
| `phi com` | `phi 计算 <定数> <acc>` | 根据分数、准确率和定数计算单曲 RKS。 |
| `phi live` |  | 查看在线服务状态与公告信息。 |
| `phi renderdiag` | `phi 渲染诊断` | 查看 HTML/T2I 渲染诊断信息。 |
| `phi guess` | `phi 猜曲绘` | 开始猜曲绘小游戏，或回答当前猜歌；支持提示、公布答案和原版 guess 模板渲染。 |
| `phi tipgame` | `phi 提示猜曲` | 开始提示猜歌小游戏；`phi tip` 获取下一条提示，`phi ans` 公布答案。 |
| `phi ltr` | `phi letter` / `phi 开字母` | 开始开字母猜歌小游戏，按 `n1 <曲名>` 回答指定编号。 |
| `phi tip` | `phi 提示` | 获取当前小游戏提示。 |
| `phi ans` | `phi 答案` / `phi 结束` | 公布当前小游戏答案并结束游戏。 |
| `phi open` | `phi 打开 A` / `phi 翻开 A` / `phi 揭开 A` | 在开字母猜歌中翻开指定字符。 |
| `phi sign` | `phi signin` / `phi 签到` / `phi 打卡` | 每日签到领取 Notes。 |
| `phi task` | `phi tasks` / `phi 我的任务` | 查看今日任务与完成进度。 |
| `phi retask` | `phi 刷新任务` | 刷新今日任务。 |
| `phi send` | `phi 送` / `phi 转` | 向其他用户转账 Notes，支持 QQ 号或 @。 |
| `phi jrrp` | `phi 今日人品` | 抽取今日人品与推荐曲目。 |
| `phi theme` |  | 设置或查看个人渲染主题，当前会影响已迁移到主题数据链路的图片命令。 |
| `phi myset` | `phi mysetting` / `phi 用户设置` / `phi 个人设置` | 查看或修改个人插件设置。 |
| `phi down` | `phi download` / `phi downill` / `phi 下载` / `phi 下载曲绘` / `phi 更新曲绘` | 下载或更新插件资源、Jinja2 模板、原版 info/otherill 资源和曲绘资源。 |

## 与原版的主要差异

- 原版 README 中的 `#` 和 `/` 触发头不由插件自行处理，AstrBot 版只注册 `phi` 命令组和顶层 `pgr` 快捷命令。
- 原版 `#phi update` 描述为更新存档；AstrBot 版保留同步存档副作用，并以“进步情况”作为主要返回内容。
- 原版本地资源目录不随 AstrBot 插件包分发；AstrBot 版会下载资源到 AstrBot 插件数据目录下的 `downloads/`。
- 原版 Puppeteer/渲染流程迁移为 AstrBot 官方 HTML/T2I 渲染接口，模板来源为 Jinja2 HTML 模板仓库和原版资源。
- 原版小游戏直接回复能力在 AstrBot 版中由配置项 `game_reply_listener` 控制；关闭时仍可使用 `phi guess <曲名>`、`phi tip`、`phi ans`、`phi open A` 等命令方式。
- 原版管理类命令如备份/恢复、插件自更新、禁用功能分组、Puppeteer 重启等不完全适配 AstrBot 插件运行方式，目前未作为主要功能迁移。

## 资源与曲绘

`illustration_source` 配置控制曲绘传入渲染链路的方式。默认 `remote` 模式会把 `Catrong/phi-plugin-ill` 的 GitHub raw URL 传给 Jinja2/T2I；`local` 模式会读取 `downloads/original_ill` 下已下载的曲绘并转成 base64。字体、CSS 图片、头像、评级图标等非曲绘资源仍会在本地内联。

如果配置了 `illustration_url_proxy`，远程曲绘 URL 会在传给 T2I 前加上代理前缀。`github_proxy` 则用于资源仓库和曲绘仓库的下载加速。

## 绑定与数据

`phi bind <sessionToken>` 会先保存 token，再尝试调用查询 API 补齐 internal_id，并立即拉取一次存档写入 AstrBot 数据目录。`phi bind <查询ID>` 会按 API ID 方式绑定并清理旧 token，避免凭据冲突。`phi bind qrcode` 支持 TapTap 二维码登录。

`phi auth <API Token>` 会调用 `/getPgrToken` 获取用户 sessionToken 并保存到 AstrBot 插件数据目录，随后自动同步一次存档。为降低泄露风险，AstrBot 版不会在聊天中明文输出完整 sessionToken；需要确认本地状态时可使用 `phi sessiontoken` 查看脱敏信息。

`phi update` 会优先合并查询平台返回的历史记录，接口不可用时回退到本地历史。本地历史记录写入 AstrBot 数据目录下的 `history/`，解绑或换绑账号时会随缓存一起清理，避免不同账号的进步记录串档。

## 本地验证

```powershell
python -m py_compile main.py phi_core\config.py phi_core\concurrency.py
python scripts\smoke_command_routes.py
python scripts\smoke_command_locks.py
python scripts\smoke_game_reply_listener.py
python scripts\smoke_dispatch.py
```
