# AstrBot Phi Plugin 开发者逻辑链路

本文记录当前 AstrBot Phi Plugin 的运行结构、数据流、资源流、渲染流和扩展方式。旧的迁移状态文档已经删除，后续维护请以本文和源码为准。

## 1. 项目定位

本插件是 `phi-plugin` 的 AstrBot 原生迁移版。它不再依赖 Yunzai、Redis、Node.js 或自建 Puppeteer，而是使用 AstrBot 的命令注册、插件数据目录、配置面板和 HTML/T2I 渲染接口。

| 能力 | 当前实现 |
|---|---|
| 命令入口 | `main.py` 使用 `@filter.command_group("phi")` 注册命令组，并注册顶层 `pgr` 快捷命令。 |
| 命令分发 | 每个命令位于 `phi_core/commands/<command>.py`，模块提供 `ALIASES` 和 `handle(ctx, user_id, args)`。 |
| 数据目录 | 用户数据、下载资源、渲染缓存写入 `StarTools.get_data_dir("astrbot_plugin_phi_plugin")`。 |
| 曲库资源 | 缺失时自动拉取，可通过 `phi down resources` 手动更新，也可配置后台定时更新。 |
| 曲绘资源 | 默认远程曲绘模式，向 T2I 传 GitHub raw URL；本地模式读取 `downloads/original_ill` 并转 base64。 |
| 渲染 | 命令数据进入 Jinja2 模板链路，最终由 AstrBot `Star.html_render` 和远端 T2I 服务截图。 |
| 图片发送 | 先发原图，失败后尝试 JPG，再失败尝试 WebP，全部失败则发送文本提示。 |
| 小游戏 | `guess`、`tipgame`、`ltr` 共用会话状态，可选开启普通消息监听。 |

## 2. 目录职责

| 路径 | 主要职责 |
|---|---|
| `main.py` | AstrBot 插件入口、命令注册、生命周期、命令锁、事件监听、发送结果。 |
| `_conf_schema.json` | AstrBot 配置面板字段。 |
| `phi_core/config.py` | 配置归一化、默认值、范围限制。 |
| `phi_core/paths.py` | 生成插件数据目录、下载目录、缓存目录和渲染缓存路径。 |
| `phi_core/commands/__init__.py` | 自动加载命令模块，构建别名路由表，处理动态 `bN/pN/xN/fcN/arcgrosbN`。 |
| `phi_core/commands/common.py` | `CommandContext`、`CommandResult` 和命令通用资源查找方法。 |
| `phi_core/commands/_sync.py` | 同步云端存档、标准化存档、合并并上传历史记录。 |
| `phi_core/commands/_bind_common.py` | sessionToken、查询 ID、TapTap 二维码绑定公共逻辑。 |
| `phi_core/commands/_b30_common.py` | `pgr`、`b30`、`rks` 共用 B30/RKS 逻辑。 |
| `phi_core/commands/_games.py` | 猜曲绘、提示猜歌、开字母小游戏状态机。 |
| `phi_core/data/loader.py` | 从原版 `info` 资源构建曲库和别名索引。 |
| `phi_core/data/ill_download.py` | 拉取模板资源、原版 `info/otherill`、曲绘仓库。 |
| `phi_core/data/illustrations.py` | 曲绘本地查找、远程 URL、代理 URL 和随机背景选择。 |
| `phi_core/save/store.py` | 绑定、存档、历史、Notes、用户设置、自定义别名等本地持久化。 |
| `phi_core/save/client.py` | 联合查分 API、排行榜、评论、TapTap 公告/更新日志等 HTTP 接口。 |
| `phi_core/save/taptap.py` | TapTap device code 二维码登录和 LeanCloud sessionToken 换取。 |
| `phi_core/query/*` | B30、RKS、成绩筛选、推分、历史进步、用户统计等纯计算逻辑。 |
| `phi_core/render/jinja_adapter.py` | 把 Python 业务对象转成原版模板期望的数据结构。 |
| `phi_core/render/jinja_renderer.py` | 读取 Jinja2 模板，内联 CSS/JS/字体/本地资源，生成可交给 AstrBot 的模板。 |
| `phi_core/render/panel.py` | 调用 AstrBot `html_render`，传递 T2I 选项，处理重试、缓存和右边界裁剪。 |
| `phi_core/render/send_variants.py` | 构建原图、JPG、WebP 三种发送候选。 |
| `scripts/smoke_*.py` | 本地 smoke 验证脚本。 |

## 3. 插件启动链路

启动入口在 `main.py::AstrBotPhiPlugin.__init__`。

```text
AstrBot 加载插件
  -> PluginConfig.from_astrbot(config)
  -> PluginPaths.from_root(root, data_dir=StarTools.get_data_dir(...))
  -> paths.ensure_data_dir()
  -> ensure_resources_blocking(config, paths)
  -> load_catalog(paths.info)
  -> SaveStore(paths.data_dir)
  -> apply_aliases(catalog, store.load_custom_aliases())
  -> SongSearcher(catalog)
  -> PhiApiClient(config)
  -> TapTapQrLogin(config, paths)
  -> CommandContext(...)
```

关键点如下。

| 步骤 | 说明 |
|---|---|
| 配置读取 | `PluginConfig.from_astrbot()` 会规范化配置项，例如非法 `render_mode` 回退到 `image`，非法曲绘模式回退到 `remote`。 |
| 路径初始化 | 插件源码目录只放代码；下载资源、缓存和用户数据全部在 AstrBot 数据目录。 |
| 资源兜底 | `ensure_resources_blocking()` 只在资源缺失时同步拉取基础资源，避免插件首次安装后曲库为空。 |
| 曲库加载 | `load_catalog()` 读取 `downloads/info`，并合并原版别名和用户自定义别名。 |
| 运行上下文 | `CommandContext` 持有配置、路径、曲库、搜索器、存储、API 客户端、渲染函数和资源锁。 |

插件生命周期还包含自动资源更新。

```text
initialize()
  -> 如果 auto_update_resources=false，直接返回
  -> 创建后台任务 _auto_update_resources_loop()
  -> 延迟 30 秒执行首次 update_resources()
  -> 每 24 小时重复一次
  -> 更新成功后 _reload_runtime_resources()

terminate()
  -> 取消后台任务
```

自动更新只更新 `downloads/html`、`downloads/info`、`downloads/otherill`，不会自动下载完整曲绘仓库。完整曲绘仓库很大，仍由 `phi down ill` 手动触发。

## 4. 命令注册与分发链路

AstrBot 必须能看到显式注册的命令，所以 `main.py` 内为每个命令写了一个包装方法。

```text
用户发送消息
  -> AstrBot 匹配 @filter.command_group("phi") 或顶层 @filter.command("pgr")
  -> main.py 对应包装方法调用 _dispatch_phi_command(event, command)
  -> event.stop_event()
  -> _extract_command_args(...)
  -> _run_with_command_locks(...)
  -> _run_phi_command(...)
  -> commands.dispatch(ctx, sender_id, command, args)
  -> 具体命令模块 handle(ctx, user_id, args)
  -> CommandResult.text(...) 或 CommandResult.image(...)
  -> _send_command_result(...)
```

命令模块约定如下。

```python
ALIASES = {"example", "示例"}

async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    ...
```

`phi_core/commands/__init__.py` 会自动扫描 `phi_core/commands` 下的模块。模块名以下划线开头或没有 `ALIASES`/`handle` 时不会加入路由。动态命令由 `_dynamic_score_command()` 处理。

| 输入形式 | 路由到 | 参数改写 |
|---|---|---|
| `phi b45` | `b30` | `args` 前插入 `45` |
| `phi p50` | `p30` | `args` 前插入 `50` |
| `phi x20` | `x30` | `args` 前插入 `20` |
| `phi fc40` | `fc30` | `args` 前插入 `40` |
| `phi arcgrosb30` | `arcgros` | `args` 前插入 `30` |

并发控制由三层锁完成。

| 锁 | 位置 | 作用 |
|---|---|---|
| 用户命令锁 | `main.py::_user_command_locks` | 同一用户的命令串行执行，避免同时读写同一份存档、历史、Notes。 |
| 小游戏会话锁 | `main.py::_game_session_locks` | `guess/tipgame/ltr/tip/ans/open` 和普通消息监听按会话串行，避免同一个游戏状态被并发修改。 |
| 资源访问锁 | `main.py::_resource_access_lock` | 更新资源和组装 Jinja2 payload 互斥，避免复制资源时渲染读到半截文件。 |

## 5. 配置项链路

配置入口是 `_conf_schema.json`，运行时读取在 `PluginConfig.from_astrbot()`。

| 配置项 | 影响链路 |
|---|---|
| `default_global` | 绑定和同步时默认选择国际服。 |
| `render_mode` | `image` 走 HTML/T2I，`text` 直接返回纯文本。 |
| `score_image_version` | `phi score` 选择现代模板或旧版模板。 |
| `ranklist_image_version` | `phi ranklist` 选择现代模板或旧版模板。 |
| `max_b30` | B30/RKS 默认展示上限，最低保持 33。 |
| `list_score_max_num` | `phi list` 最大展示条数。 |
| `history_day_num` | `phi update` 每日最多展示的成绩变化条数。 |
| `history_score_date` | `phi update` 最多展示最近多少个有变化日期。 |
| `history_score_num` | `phi update` 总成绩变化展示上限。 |
| `api_base_url` | 联合查分 API 根地址。 |
| `request_timeout` | API、TapTap、TapTap 公告等 HTTP 请求超时。 |
| `qrcode_timeout` | TapTap 二维码轮询等待时间。 |
| `render_max_retries` | T2I 渲染失败后的额外重试次数。 |
| `send_render_wait_message` | 是否在图片渲染命令开始时发送等待提示，并在完成后尝试撤回。 |
| `render_wait_message` | 图片渲染等待提示的文本内容。 |
| `render_selector_screenshot` | 向 T2I 传 `selector=#container`，优先按容器截图。 |
| `render_wait_for_resources` | 向 T2I 传 `wait_for_resources=true`，截图前等待图片和字体。 |
| `render_resource_timeout` | 等待远程资源的最长毫秒数。 |
| `github_proxy` | 资源仓库克隆和远程曲绘下载代理。 |
| `auto_update_resources` | 是否启用后台定时更新模板、info、otherill。 |
| `illustration_source` | 曲绘使用 `remote` 在线 URL 或 `local` 本地 base64。 |
| `illustration_url_proxy` | 只影响传给 T2I 的远程曲绘 URL。 |
| `game_reply_listener` | 小游戏是否监听普通消息直接回复。 |
| `quote_reply` | 插件回复是否引用触发命令的消息，影响文本、图片和中间提示消息。 |

## 6. 资源下载与自动更新链路

资源相关代码在 `phi_core/data/ill_download.py`。

```text
ensure_resources_blocking()
  -> resources_ready(paths) 检查 info、help、b19/help 模板和 otherill
  -> 缺失时 update_resources_blocking()

update_resources()
  -> _RESOURCE_UPDATE_LOCK 全局互斥
  -> 拉取或更新 Catrong/phi-plugin sparse resources
  -> 拉取或更新 kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template
  -> 复制 resources/info 到 downloads/info
  -> 复制 resources/otherill 到 downloads/otherill
  -> 复制 Jinja2 模板仓库到 downloads/html

update_illustrations()
  -> 拉取或更新 Catrong/phi-plugin-ill
  -> 保存到 downloads/original_ill
```

手动命令链路如下。

| 命令 | 调用 | 说明 |
|---|---|---|
| `phi down resources` | `_download_resources()` -> `update_resources()` | 更新模板、info、otherill，成功后调用 `ctx.reload_resources()`。 |
| `phi down ill` | `_download_illustrations()` -> `update_illustrations()` | 更新完整曲绘仓库。 |
| `phi down all` | 先资源，后曲绘 | 资源更新会重载曲库，曲绘更新不需要重载曲库。 |

资源更新和渲染读资源通过 `ctx.resource_lock` 互斥。注意这个锁只包住复制资源与组装模板，不会包住远程 T2I 截图，避免一次慢截图阻塞太久。

## 7. 曲库与曲绘链路

曲库加载入口是 `load_catalog(paths.info)`。

```text
downloads/info/info.csv
  + downloads/info/difficulty.csv
  + downloads/info/infolist.json
  + downloads/info/spinfo.json
  + downloads/info/otherinfo.yaml
  + downloads/info/nicklist.yaml
  + downloads/info/notesInfo.json
  -> SongCatalog(songs, alias_to_id)
  -> apply_aliases(catalog, user custom_aliases.yaml)
  -> SongSearcher(catalog)
```

曲绘来源由 `CommandContext.illustration_source(song)` 决定。

| 模式 | 返回值 | 典型用途 |
|---|---|---|
| `illustration_source=remote` | GitHub raw URL 或经过 `illustration_url_proxy` 的 URL | 传给远端 T2I，由服务端下载曲绘。 |
| `illustration_source=local` | 本地 `Path` | 由 `original.image_data_uri()` 转成 `data:*;base64,...`。 |

`download_proxy=True` 时使用 `github_proxy` 生成下载 URL，主要用于猜曲绘这类运行时需要实时拉取曲绘字节的场景。`illustration_url_proxy` 只用于把资源 URL 传给 T2I 渲染的场景。

## 8. 绑定与存档同步链路

绑定公共逻辑在 `_bind_common.py`。

```text
phi bind <sessionToken>
  -> validate_token
  -> store.bind(user_id, token)
  -> client.bind_user(platform=AstrBot, platform_id=user_id, token=...)
  -> store.set_api_id(...)
  -> sync_save_with_progress()
  -> 返回绑定成功 + 自动同步结果

phi bind <查询ID>
  -> client.bind_user(..., api_user_id=...)
  -> store.set_api_id(...)
  -> clear_token / clear_snapshot / clear_history
  -> sync_save_with_progress()

phi bind qrcode
  -> TapTapQrLogin.request_qrcode()
  -> 发送二维码图片和说明
  -> wait_for_session_token()
  -> _bind_token(...)

phi auth <API Token>
  -> client.get_pgr_token()
  -> store.bind(...)
  -> store.set_api_id(...)
  -> sync_save_with_progress()
```

同步逻辑在 `_sync.py`。

```text
sync_save_cache(ctx, user_id)
  -> 读取旧 snapshot
  -> 读取 token/api_id
  -> client.fetch_cloud_save(token 或 api_id)
  -> normalize_save(...)
  -> 保存 saves/<user>.json
  -> 尝试 apply_task_rewards(...)
  -> 返回 SaveSyncResult

sync_save_with_progress(ctx, user_id)
  -> sync_save_cache(...)
  -> store.load_history(user_id)
  -> client.fetch_history(..., fields=[data,rks,scoreHistory,challengeModeRank])
  -> merge_histories(remote_history, local_history)
  -> update_progress_history(...)
  -> store.save_history(...)
  -> client.set_history(...) 尽力回传
```

B30/RKS 查询会优先自动同步一次。`_b30_common._load_latest_or_cached_snapshot()` 在 API 失败时，如果本地已有缓存，会记录日志并使用缓存；没有缓存才返回无可用存档。

## 9. 查询与计算链路

纯计算尽量集中在 `phi_core/query`，命令文件只做解析、取数据和选择模板。

| 模块 | 职责 |
|---|---|
| `query/b30.py` | `iter_score_records()`、`rks_from_acc()`、评级判断、`compute_b30()`。 |
| `query/filters.py` | 定数/ACC/难度/评级筛选，`list/lvsco/suggest/table/randclg` 等复用。 |
| `query/progress.py` | 历史记录归一化、远端/本地历史合并、RKS/Data/课题分曲线和成绩变化计算。 |
| `query/history.py` | 历史 B30、年度统计等历史分析。 |
| `query/score.py` | 单曲成绩过滤。 |
| `query/user_info.py` | 玩家总体统计。 |

典型 B30 链路如下。

```text
pgr/b30/rks
  -> _b30_common.render_best30()
  -> _load_latest_or_cached_snapshot()
  -> compute_b30(snapshot, catalog, limit)
  -> _attach_acc_averages() 从 API 拉平均 ACC
  -> jinja_adapter.b30_data(...)
  -> render_jinja_template(ctx, "b19/b19", ...)
```

典型 `phi update` 链路如下。

```text
update.handle()
  -> sync_save_with_progress()
  -> load_notes()
  -> maybe_refresh_daily_tasks()
  -> build_update_task_rows()
  -> jinja_adapter.update_data(...)
  -> render_jinja_template(ctx, "update/update", ..., width=800)
```

## 10. Jinja2 渲染链路

当前主要渲染入口是 `phi_core/commands/_rendering.py::render_jinja_template()`。

```text
命令模块
  -> jinja_adapter.<template>_data(ctx.paths, ...)
  -> render_jinja_template(ctx, "folder/template", data, name, width=?, height=?)
  -> _apply_user_theme(...)
  -> 如果主题为 dss2 且模板是 b19/b19，切换到 b19/dss2
  -> ctx.resource_lock 保护 _build_jinja_payload()
  -> jinja_adapter.adapt_template_data(...)
  -> jinja_renderer.render_template_payload(...)
  -> render_original_html(...)
  -> panel.render_html(...)
  -> AstrBot Star.html_render(template, data, False, options)
  -> T2I 返回图片路径或图片 bytes
  -> panel 校验图片、必要时裁剪右边界
  -> CommandResult.image(path)
```

这里有一个重要设计点：插件不会在本地把业务数据完整填充成最终 HTML 再交给 AstrBot。`jinja_renderer.render_template_payload()` 返回的是已经内联静态资源、但仍保留业务变量的 Jinja2 模板和 JSON 数据。最终变量填充由 AstrBot 的 `html_render` 完成。

`jinja_renderer.py` 的职责如下。

| 函数 | 作用 |
|---|---|
| `template_root()` | 优先选择 `downloads/html`，找不到时才使用开发期 fallback 路径。 |
| `_template_source()` | 处理简单的 `{% extends %}` 和 `{% block %}`，把父子模板展平。 |
| `_rewrite_template_asset_fields()` | 把模板里动态拼接资源文件名的表达式改成 Python 预处理字段。 |
| `make_self_contained()` | 内联 CSS、JS、本地图片、字体，注入 viewport、`#container` 和 reset CSS。 |
| `_inline_resource_attributes()` | 处理 `src=`、`href=`。 |
| `_inline_css_urls()` | 处理 CSS `url(...)` 和 `@import`。 |
| `_ensure_screenshot_container()` | 确保远端 T2I 可用 `#container` 做 selector screenshot。 |

`panel.py` 的职责如下。

| 函数 | 作用 |
|---|---|
| `_render_with_retries()` | 按 `render_max_retries` 自动重试偶发 T2I 断连。 |
| `_options()` | 组装传给 T2I 的截图参数。 |
| `_render_result_path()` | 兼容 AstrBot 返回路径或 bytes 两种情况。 |
| `_is_valid_image_file()` | 防止 T2I 返回 HTML 错误页却被当成图片发送。 |
| `_trim_right_border()` | 对小图尝试裁掉纯黑/纯白右边界。 |
| `_prune_render_cache()` | 每小时清理一次 24 小时以前的 `html-*` 渲染缓存。 |

## 11. 模板数据适配规则

`jinja_adapter.py` 是当前模板迁移的核心，不要把字段拼接逻辑重新散落到命令模块里。

| 规则 | 原因 |
|---|---|
| 命令模块只负责业务数据获取和选择模板。 | 命令保持薄，便于维护和测试。 |
| 原版模板需要的字段尽量在 adapter 中生成。 | Jinja2 和 art-template/JavaScript 的表达式语义不同。 |
| 动态资源文件名在 Python 里预处理成字段。 | 远端 T2I 不能读取本地路径，也不适合在模板里拼复杂路径。 |
| 本地图片、CSS 背景、字体、脚本必须内联成 data URI。 | 远端 T2I 无法访问 AstrBot 本地文件系统。 |
| 远程曲绘 URL 是例外。 | `illustration_source=remote` 时允许把 GitHub raw URL 交给 T2I 下载。 |
| 复杂数值计算放在 Python。 | Jinja2 模板只做展示循环和简单判断。 |
| 新模板优先复用原版字段名。 | 降低与上游模板仓库差异。 |

常见模板入口如下。

| 模板 | 命令 | Adapter 数据入口 |
|---|---|---|
| `help/help` | `phi help` | `help_data()` |
| `b19/b19` | `pgr`、`phi pgr`、`phi b30`、`phi rks`、`phi bN` | `b30_data()` |
| `b19/dss2` | `phi p30`、`phi x30`、`phi fc30`、`phi lmtacc` | `dss2_record_list_data()` |
| `arcgrosB19/arcgrosB19` | `phi arcgros`、`phi arcgrosbN` | `arcgros_b19_data()` |
| `update/update` | `phi update` | `update_data()` |
| `userinfo/userinfo` | `phi info`、`phi info1`、`phi info2` | `userinfo_data()` |
| `score/score`、`score/scoreOld` | `phi score` | `score_data()` |
| `list/list` | `phi list` | `list_data()` |
| `suggest/suggest` | `phi suggest` | `suggest_data()` |
| `table/table` | `phi table` | `table_data()` |
| `lvsco/lvsco` | `phi lvscore` | `lvscore_data()` |
| `chap/chap` | `phi chap` | `chap_data()` |
| `historyB30/historyB30` | `phi hisb30` | `history_b30_data()` |
| `analyzeSaveHistory/analyzeSaveHistory` | `phi 2025history` | `analyze_save_history_data()` |
| `atlas/atlas` | `phi song`、猜曲绘答案第二张图 | `atlas_data()` |
| `chartInfo/chartInfo` | `phi chart` | `chart_info_data()` |
| `rand/rand` | `phi rand` | `rand_data()` |
| `clg/clg` | `phi randclg` | `clg_data()` |
| `rankingList/rankingList` | `phi ranklist` | `ranking_list_data()` |
| `rankingList-old/rankingList` | `phi ranklist` 旧版模式 | `ranking_list_old_data()` |
| `setting/userSetting` | `phi myset` | `user_setting_data()` |
| `ill/ill` | `phi ill` | `ill_data()` |
| `jrrp/jrrp` | `phi jrrp` | `jrrp_data()` |
| `sign/sign` | `phi sign`、`phi task`、`phi retask` | `sign_data()` |
| `newSong/newSong` | `phi newlog` | `newlog_data()` |
| `guess/guess` | `phi guess`、`phi tipgame` 最终曲绘提示 | `guess_data()` |

## 12. 图片发送链路

命令返回 `CommandResult.image(path)` 后，`main.py::_send_image_with_fallback()` 负责发送。

```text
CommandResult.image(path)
  -> 可选：main.py::_send_render_wait_message() 发送等待提示
  -> build_image_send_variant(path, "original")
  -> Comp.Image.fromBytes(bytes) 或 Comp.Image.fromBase64(...)
  -> event.chain_result([Image])
  -> event.send(...)
  -> 如果失败，转换 JPG 再发
  -> 如果仍失败，转换 WebP 再发
  -> 如果全部失败，发送文本错误提示
  -> 可选：main.py::_recall_message() 撤回等待提示
```

注意事项如下。

| 点 | 说明 |
|---|---|
| 不发送 `file:///...` | 一些 QQ/OneBot 平台会因为富媒体转存失败报错。当前直接发送 bytes/base64。 |
| JPG/WebP 会压缩 | `send_variants.py` 限制最大边长和最大像素，降低平台传输失败概率。 |
| 透明图会铺白底 | 有透明通道的图片在转 JPG/WebP 前会先合成白底。 |
| T2I 错误页不会直接发 | `panel._is_valid_image_file()` 会验证图片，不让 HTML 错误页伪装成图片。 |
| 等待提示撤回依赖平台 | 只有 `event.send()` 返回可解析的 `message_id`，且平台支持 `delete_msg` 或 `call_action("delete_msg")` 时才会撤回。取不到 ID 时不会阻断最终图片发送。 |

## 13. 小游戏链路

小游戏状态集中在 `_games.py` 的 `_ACTIVE_GAMES`。

| 游戏 | 状态类 | 开始命令 | 回答方式 |
|---|---|---|---|
| 猜曲绘 | `GuessIllGame` | `phi guess` | `phi guess <曲名>`，或开启监听后直接回复曲名。 |
| 提示猜歌 | `TipGame` | `phi tipgame` | `phi guess <曲名>`，`phi tip` 获取下一条提示。 |
| 开字母猜歌 | `LetterGame` | `phi ltr` | `phi ltr n1 <曲名>`，`phi open A` 翻开字符。 |

会话 key 使用 `ctx.session_id`，没有时使用 `user_id`。AstrBot 普通消息监听入口在 `main.py::phi_game_reply_listener()`，只有配置 `game_reply_listener=true` 且当前会话存在游戏时才接管普通消息。

猜曲绘公布答案时，如果有 `ctx.sender`，会并行渲染两张图片。

```text
_finish_with_answer()
  -> create_task(_render_guess_image(...))
  -> create_task(render_jinja_template(..., "atlas/atlas"))
  -> gather(...)
  -> 先发文字
  -> 发曲绘答案图
  -> 返回曲目详情图
```

## 14. 文本与图片模式

绝大多数命令遵循以下模式。

```text
if ctx.config.render_mode == "image" and ctx.html_render is not None:
    return CommandResult.image(await render_jinja_template(...))
return CommandResult.text(...)
```

纯文本命令不要再丢给 T2I 转图。例如 `phi best` 是文字版 B30，`phi data`、`phi id`、`phi api`、`phi sessiontoken` 等直接发送文本。

## 15. 新增命令流程

新增命令时按下面顺序做。

1. 在 `phi_core/commands/<name>.py` 新建模块。
2. 定义 `ALIASES` 和 `handle(ctx, user_id, args)`。
3. 如果需要 AstrBot 原生命令注册，在 `main.py` 的 `phi` 命令组里添加包装方法和 `desc`。
4. 如果命令可动态改写，例如 `xxx30`，在 `commands/__init__.py::_dynamic_score_command()` 补规则。
5. 业务计算优先放到 `phi_core/query`，不要堆在命令模块。
6. 需要存档时优先用 `ctx.load_snapshot()`、`sync_save_cache()` 或 `sync_save_with_progress()`。
7. 需要 API 时优先给 `PhiApiClient` 增加方法，命令模块不要直接散写 HTTP 请求。
8. 需要渲染时先在模板仓库准备 Jinja2 模板，再在 `jinja_adapter.py` 增加数据入口。
9. 命令返回 `CommandResult.text()` 或 `CommandResult.image()`，不要直接调用 `event.send()`，除非是需要中间消息的长流程并通过 `ctx.sender`。
10. 更新 smoke 或增加新 smoke，至少跑命令注册和分发检查。

推荐最小命令模板如下。

```python
from __future__ import annotations

from .common import CommandContext, CommandResult

ALIASES = {"demo", "演示"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    text = args.strip()
    if not text:
        return CommandResult.text("请提供参数。")
    return CommandResult.text(f"收到：{text}")
```

## 16. 新增渲染模板流程

新增或迁移一个模板时按下面顺序做。

1. 确认模板文件已在模板仓库中存在，并会被下载到 `downloads/html/<folder>/<template>.html`。
2. 模板中的静态资源尽量使用相对路径，让 `jinja_renderer.py` 负责内联。
3. 模板中动态文件名不要拼本地路径，改成字段，例如 `avatarImg`、`challengeImg`、`background`、`illustration`。
4. 在 `jinja_adapter.py` 添加 `<template>_data()`，负责把命令数据转成模板字段。
5. 如果模板还需要二次兜底，在 `adapt_template_data()` 中按模板路径分发到 `prepare_<template>_data()`。
6. 命令模块调用 `render_jinja_template(ctx, "folder/template", data, name, width=?, height=?)`。
7. 如果截图尺寸异常，优先检查模板是否有 `#container`，其次检查 `_viewport_width`、`_viewport_height` 和 T2I selector 选项。
8. 如果背景回退到模板内置图，优先检查 adapter 传入的 `background` 是否为空、是否被 CSS 覆盖、是否被远程 URL 保留逻辑误处理。

## 17. 调试与验证

常用 smoke 命令如下。

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m py_compile main.py phi_core\config.py phi_core\commands\__init__.py phi_core\commands\_rendering.py phi_core\render\jinja_renderer.py phi_core\render\jinja_adapter.py phi_core\render\panel.py
python scripts\smoke_command_group.py
python scripts\smoke_command_routes.py
python scripts\smoke_command_locks.py
python scripts\smoke_game_reply_listener.py
python scripts\smoke_resource_download.py
python scripts\smoke_jinja_render_chain.py
python scripts\smoke_dispatch.py
python scripts\smoke_image_send_variants.py
python scripts\smoke_image_send_fallback_flow.py
python scripts\smoke_guess_answer_render_viewport.py
```

按问题类型选择验证。

| 改动类型 | 建议验证 |
|---|---|
| 命令注册或 `main.py` 包装方法 | `smoke_command_group.py`、`smoke_command_routes.py`。 |
| 用户命令并发、小游戏并发 | `smoke_command_locks.py`、`smoke_game_reply_listener.py`。 |
| 资源下载和自动更新 | `smoke_resource_download.py`。 |
| Jinja2 模板或 adapter | `smoke_jinja_render_chain.py`、`smoke_dispatch.py`。 |
| 图片发送 fallback | `smoke_image_send_variants.py`、`smoke_image_send_fallback_flow.py`。 |
| 猜曲绘答案图 | `smoke_guess_answer_render_viewport.py`。 |

编码检查建议如下。

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
from pathlib import Path
for path in Path('.').rglob('*'):
    if path.suffix.lower() not in {'.py', '.md', '.json', '.yaml', '.yml'}:
        continue
    data = path.read_bytes()
    if data.startswith(b'\xef\xbb\xbf'):
        print('UTF-8 BOM:', path)
'@ | python -
```

PowerShell 直接输出中文时可能受终端编码影响。判断文件是否损坏时，以 Python `Path.read_text(encoding="utf-8")` 的结果为准。

## 18. 常见问题定位

| 现象 | 优先检查 |
|---|---|
| 新命令 AstrBot 不识别 | `main.py` 是否注册了 `@phi.command`，命令模块是否有 `ALIASES` 和 `handle`。 |
| `dispatch` 找不到命令 | `commands/__init__.py` 是否能扫描到模块，别名是否 `casefold()` 后一致。 |
| 首次安装曲库为空 | `downloads/info` 是否存在，`ensure_resources_blocking()` 是否成功拉取资源。 |
| 资源更新后曲库没变 | `ctx.reload_resources()` 是否被调用，是否拿到了 `resource_lock`。 |
| 图片背景是模板默认图 | adapter 的 `background` 字段是否为空，远程曲绘 URL 是否被错误转义或内联失败。 |
| 图片右侧多黑边/白边 | T2I 是否支持 selector screenshot，模板是否有 `#container`，`panel._trim_right_border()` 是否因图片过大跳过。 |
| T2I 返回 HTML 错误页 | `panel._is_valid_image_file()` 日志会显示 first bytes，检查远端 T2I 服务或网络。 |
| QQ 富媒体发送失败 | 发送链路应走 bytes/base64；若原图失败，看 JPG/WebP fallback 日志。 |
| 绑定后玩家名是 user | 检查 `normalize_save()` 的 `saveInfo.PlayerId`、`nickname`、`gameuser.name` 字段解析。 |
| `phi update` 历史太短 | 检查 `client.fetch_history()` 是否成功，`merge_histories()` 是否合并远端和本地历史。 |
| 小游戏普通回复没反应 | 配置 `game_reply_listener`、`ActivePhiGameFilter.enabled` 和 `_ACTIVE_GAMES` 会话 key。 |

## 19. 维护原则

| 原则 | 说明 |
|---|---|
| 命令模块保持薄 | 命令模块不堆 HTML、不堆复杂计算、不直接散写 HTTP。 |
| Adapter 集中模板字段 | 原版模板字段差异统一在 `jinja_adapter.py` 处理。 |
| 不传本地路径给远端 T2I | 除远程曲绘 URL 外，资源必须内联为 data URI。 |
| 用户数据只写 AstrBot 数据目录 | 不把绑定、历史、缓存写入源码目录。 |
| 资源更新要可重载 | 更新 `info/html/otherill` 后必须刷新 `catalog/searcher`。 |
| 纯文本保持纯文本 | 不把文字命令交给 T2I。 |
| 先 smoke 再宣称完成 | 至少跑与改动相关的 smoke，避免“看起来能跑”。 |
