# Jinja2 Template Data Adapter Notes

本文档记录从原版 `art-template` 迁移到 Jinja2 后，数据适配层需要承担的职责。

迁移命令时请优先阅读本文件，再改 `phi_core/render/jinja_adapter.py`。这里记录的是模板语义差异和容易踩坑的地方，不是一次性阶段文档。

## 适配层位置

- 运行时入口：`phi_core/commands/_rendering.py::render_jinja_template`
- 数据集中适配：`phi_core/render/jinja_adapter.py`
- HTML 渲染与资源内联：`phi_core/render/jinja_renderer.py`
- 命令处理文件只负责获取业务数据、选择模板路径、调用适配函数和渲染函数。

标准链路：

```text
command handler
  -> jinja_adapter.<template>_data(...)
  -> render_jinja_template(ctx, "<folder>/<template>", data, name)
  -> jinja_adapter.adapt_template_data(...)
  -> jinja_renderer.render_template(...)
  -> inline CSS / JS / images / fonts as base64 data URIs
  -> panel.render_html(...)
  -> AstrBot html_render / t2i
```

## 为什么需要数据适配层

原版 `.art` 模板运行在 JavaScript/art-template 环境中，模板里常见这些行为：

- 直接调用 JS 表达式、三元表达式、数组方法或对象方法。
- 在模板循环中临时累加、修改变量。
- 依赖 `undefined`、空字符串、数字和对象之间的 JS 宽松转换。
- 依赖资源路径能被 Puppeteer 在本地读取。

Jinja2 和远端 AstrBot t2i 不具备这些前提，所以迁移后要把这些行为提前放到 Python 适配层里完成。

## 总规则

- 不要在命令文件里硬编码 HTML 结构。
- 不要在命令文件里散落模板字段转换逻辑。
- 不要向模板传本地文件路径作为图片资源。
- 所有本地图片、CSS 背景图、字体、脚本都必须在 `jinja_renderer.py` 内联为 `data:*;base64,...`。
- Jinja2 模板应尽量只做展示判断和循环，不承担复杂计算。
- 若某个模板需要特殊预处理，在 `adapt_template_data(...)` 中按模板路径分发。
- 新增适配函数时，优先使用原版字段名，减少模板和原版差异。

## 已确认需要预处理的模板

| Template | Adapter | 预处理职责 |
|---|---|---|
| `help/help` | `help_data` | 读取 `help.json`，注入 `cmdHead`、`isMaster`、随机背景。 |
| `b19/b19` | `b30_data` | 构造 `gameuser`、`phi`、`b19_list`、`stats`、`spInfo`，选择与成绩相关的随机背景。 |
| `arcgrosB19/arcgrosB19` | `arcgros_b19_data` + `prepare_arcgros_b19_data` | 复用 B30 数据并截取 B19；预格式化 `song.std_score`。 |
| `b19/dss2` | `dss2_record_list_data` + `prepare_dss2_data` | 构造记录列表、头图、RKS、特殊说明；保证 `phi` 和 `b19_list` 至少为空列表。 |
| `lvsco/lvsco` | `lvscore_data` + `prepare_lvsco_data` | 计算等级统计、进度、范围、`rating_max`。Jinja2 不能可靠复刻原模板循环内最大值累加。 |
| `newnotice/newnotice` | `newnotice_data` + `prepare_newnotice_data` | 统一公告列表字段，预格式化日期文本。 |
| `list/list` | `list_data` | 构造曲目行、难度、曲绘、评级资源名、分数、ACC、建议文本。 |
| `suggest/suggest` | `suggest_data` + `prepare_suggest_data` | 把推荐项分到 `song[0]` 至 `song[5]`，并规范 `phisong`。 |
| `table/table` | `table_data` | 按定数分组，设置 `_imgPath`，在有存档时叠加玩家成绩状态。 |
| `rankingList/rankingList` | `ranking_list_data` + `prepare_ranking_list_data` | Normalize online ranking rows, selected-player detail panel, RKS/Challenge history curves, avatar/challenge fields, base64 backgrounds, and B30 mini-card groups. |
| `rankingList-old/rankingList` | `ranking_list_old_data` + `prepare_ranking_list_old_data` | Build legacy row data with `Title`, `totDataNum`, `BotNick`, base64 profile/background/avatar assets, exact displayed rank index, save dates, self intro, and flattened B19 score chips. |
| `clg/clg` | `clg_data` + `prepare_clg_data` | Build random challenge song rows, base64 chart illustrations, total challenge value, and Tap/Drag/Hold/Flick/Combo counts from `notesInfo.json`. |
| `setting/userSetting` | `user_setting_data` + `prepare_user_setting_data` | Build page metadata, setting groups, option cards, selected markers, and random base64 background. |
| `ill/ill` | `ill_data` + `prepare_ill_data` | Convert selected illustration to base64 data URI, attach illustrator text, and reuse illustration as background. |
| `jrrp/jrrp` | `jrrp_data` + `prepare_jrrp_data` | Normalize luck/date/sentence/good/bad fields, convert background to base64 data URI, and preserve 2048x1080 viewport. |
| `sign/sign` | `sign_data` + `prepare_sign_data` | Normalize player/Notes/luck/task/calendar/notice fields, edge progress defaults, avatar name, base64 background, and base64 task illustrations. |
| `newSong/newSong` | `newlog_data` + `prepare_newlog_data` | Build upstream `ans` table rows from local/online version logs, normalize cell text/colspan/rowspan/colors, and keep the converted template free of JS template-string conditionals. |
| `guess/guess` | `guess_data` + `prepare_guess_data` | Convert cropped illustration and answer reveal images to base64 data URIs, normalize crop coordinates/filter CSS, and set explicit viewport width/height so remote t2i screenshots do not include extra area. |

## 待迁移时重点关注

| Template | 需要确认的数据 |
|---|---|
| `score/score` | 单曲成绩、历史成绩、排名列表、AP/FC 统计、曲绘、背景、曲名自适应字段。 |
| `score/scoreOld` | 旧版查分布局字段，尤其历史数据和玩家信息显示位置。 |
| `score/scoreRankList` | 在线排名列表、玩家排名高亮、分页/数量限制。 |
| `update/update` | 进步时间线、任务列表、RKS 曲线、Notes/数据变化、历史快照跨度。 |
| `userinfo/userinfo` | 新版左右两列布局、头像、real rks、长历史曲线、背景曲绘。 |
| `userinfo/userinfo-old` | 旧版布局字段和 `phi info2` 行为。 |
| `historyB30/historyB30` | 历史 B30 列表、颜色语义、RKS 变化。 |
| `analyzeSaveHistory/analyzeSaveHistory` | 年度统计、月份/日期聚合、极值和比例。 |
| `atlas/atlas` | 歌曲详情、谱面详情、曲绘、评论/别名字段。 |
| `rankingList/rankingList`, `rankingList-old/rankingList` | Already migrated: keep modern online list rows/current-user detail in `ranking_list_data`; keep legacy 800px list rows and B19 chips in `ranking_list_old_data`. |

## 资源传输规则

远端 t2i 服务不能读取本地路径，所以：

- 模板中的 `<img src="...">` 必须被转换成 base64 data URI。
- CSS 中的 `url(...)` 必须被转换成 base64 data URI。
- Exception: when `illustration_source=remote`, image references that point to `Catrong/phi-plugin-ill` may stay as GitHub raw URLs. This exception is only for song illustrations and blurred illustration backgrounds; local paths, fonts, CSS, JS, avatar images, rating icons, and other template assets must still be inlined as data URIs.
- 字体文件必须通过 CSS `@font-face` 或被 CSS 引用后内联。
- 不能依赖 `file://`、绝对路径、Docker 内部路径或 Windows 路径。
- 若背景回退到模板内置图，优先检查传入数据字段是否为空，其次检查 CSS 背景是否覆盖了数据背景。

当前内联逻辑在 `jinja_renderer.py` 中处理：

- `<link rel="stylesheet" href="...">`
- `<script src="..."></script>`
- `src="..."`
- `href="..."`
- CSS `url(...)`
- CSS `@import`

## Jinja2 与 art-template 差异注意事项

- Jinja2 循环内 `set` 的变量作用域与 JS/art-template 不同，循环内累加应放在 Python。
- JS 的 `a ? b : c` 应转换为 Jinja2 的 `b if a else c`，复杂情况放在 Python。
- JS 的 `arr.length` 应转换为 `arr|length`，或在 Python 提供 `count` 字段。
- JS 的 `obj[key]` 动态访问在 Jinja2 可用，但字段缺失时更容易变成空值；适配层应补默认值。
- JS 的数字格式化、百分比、千分位字符串应优先在 Python 生成，避免模板重复逻辑。
- 原模板中的临时计算变量若影响布局、宽度、颜色、评级图标，应在适配层显式生成。

## 迁移新命令时的步骤

1. 阅读原版 `.art` 和 `.css`，确认模板路径与字段名。
2. 阅读当前命令逻辑，确认已有业务数据来源不要被破坏。
3. 在 `jinja_adapter.py` 添加 `<template>_data(...)`，只做数据形状转换。
4. 如模板需要二次兜底，在 `adapt_template_data(...)` 添加 `prepare_<template>_data(...)`。
5. 命令文件改为调用 `render_jinja_template(ctx, "<folder>/<template>", data, name)`。
6. 更新 `docs/jinja2-migration-list.md` 和 `docs/command-migration-status.md`。
7. 运行验证命令，并检查 touched files 没有 UTF-8 BOM。

## 验证命令

```powershell
python -m py_compile phi_core\render\jinja_adapter.py phi_core\render\jinja_renderer.py phi_core\commands\_rendering.py
$env:PYTHONIOENCODING='utf-8'; python scripts\audit_jinja2_templates.py
$env:PYTHONIOENCODING='utf-8'; python scripts\smoke_jinja_render_chain.py
$env:PYTHONIOENCODING='utf-8'; python scripts\smoke_dispatch.py
```

检查 BOM：

```powershell
$files = @(
  'docs\jinja2-template-data-adapter.md',
  'docs\jinja2-migration-list.md',
  'phi_core\render\jinja_adapter.py'
)
foreach ($file in $files) {
  if (Test-Path $file) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $file))
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
      Write-Error "UTF-8 BOM found: $file"
    }
  }
}
```

## 当前维护原则

- 这份文档是长期注意事项，不应在阶段清理中删除。
- 若某条注意事项已经完全失效，应先更新本文档原因，再修改迁移列表。
- 如果新模板迁移发现新的 Jinja2/art-template 差异，请补充到本文档。
