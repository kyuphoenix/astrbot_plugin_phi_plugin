# Jinja2 Migration List

This document is the current tracking point for moving phi-plugin rendering onto the converted Jinja2 templates under `D:\astrbot_plugin_phi_plugin\jinja2`.

## Scope

- Keep command runtime data adaptation in `phi_core/render/jinja_adapter.py`.
- Keep command handlers thin: load data, select the original template path, call `render_jinja_template(...)`.
- Keep remote t2i compatibility: all local images, CSS images, scripts, and fonts must be inlined before sending HTML.
- Runtime `downloads/html` now comes from `kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template`; `downloads/info` and `downloads/otherill` still come from `Catrong/phi-plugin`.
- Use `render_jinja_template(..., width=..., height=...)` when an upstream layout needs a fixed viewport beyond the default width-only path.
- Keep `docs/command-migration-status.md` as the broader command parity table.

## Cleaned Up Documents

The following completed or superseded phase documents were removed from `docs`:

- `jinja2-render-chain.md`
- `jinja2-template-audit.md`
- `jinja2-template-comparison-checklist.md`
- `jinja2-template-migration.md`
- `pgr-render-chain.md`

Their active information has been folded into this file or `docs/command-migration-status.md`.

`jinja2-template-data-adapter.md` remains active because it records runtime adapter caveats that are easy to lose during command-by-command migration.

## Current Render Chain

```text
command handler
  -> jinja_adapter.<template>_data(...)
  -> render_jinja_template(ctx, "<folder>/<template>", data, name)
  -> jinja_adapter.adapt_template_data(...)
  -> jinja_renderer.render_template_payload(...)
  -> flatten template inheritance and inline CSS / JS / fixed local images / fonts as base64 data URIs
  -> panel.render_html(template, data, ...)
  -> AstrBot html_render runs Jinja2 with the JSON data, then t2i screenshots the result
```

Template paths use upstream names without `.art`, for example `b19/b19`, `score/score`, or `userinfo/userinfo`.

Dynamic asset filenames must be assembled in Python before calling AstrBot. Templates should receive fields such as `avatarImg`, `challengeImg`, `ratingImg`, `dataImg`, `ratingImgs`, or `help.imgSrc` instead of composing paths like `html/otherimg/{{ song.Rating }}.png` at render time. The renderer may rewrite converted upstream template expressions to these fields, but it must not locally render business data with Jinja2 before calling `html_render`.

## Runtime-Migrated Commands

| Template | Commands | Adapter entry | Status | Notes |
|---|---|---|---|---|
| `help/help` | `phi help` | `help_data` | Runtime migrated | Uses upstream help data and random blurred background. |
| `b19/b19` | `phi pgr`, `phi b30`, `phi rks`, `phi bN` | `b30_data` | Runtime migrated | Keep B30 calculation stable; do not casually change ranking logic. |
| `arcgrosB19/arcgrosB19` | `phi arcgros`, `phi arcgrosb19` | `arcgros_b19_data` | Runtime migrated | Uses `prepare_arcgros_b19_data` for preformatted score fields. |
| `lvsco/lvsco` | `phi lvscore`, `phi lvsco`, `phi scolv` | `lvscore_data` | Runtime migrated | Uses `prepare_lvsco_data` for `rating_max`. |
| `newnotice/newnotice` | `phi newnotice` | `newnotice_data` | Runtime migrated | Uses `prepare_newnotice_data` for normalized notice/date fields. |
| `b19/dss2` | `phi best`, `phi p30`, `phi x30`, `phi fc30`, `phi lmtacc` | `dss2_record_list_data` | Runtime migrated | Still needs exact upstream label/background parity. |
| `list/list` | `phi list` | `list_data` | Runtime migrated | Template conversion removes JS template-string leftovers and keeps rating assets dynamic. |
| `suggest/suggest` | `phi suggest` | `suggest_data` | Runtime migrated | Uses six Python-side suggestion buckets and normalized phi/AP rows. |
| `table/table` | `phi table` | `table_data` | Runtime migrated | Groups charts by constant and overlays score state when a cached save exists. |
| `score/score`, `score/scoreOld`, `score/scoreRankList` | `phi score` | `score_data` | Runtime migrated | Default modern path uses original `score/score`; `score_image_version=old` selects `score/scoreOld`; modern online ranklist uses the converted/inlined `scoreRankList` CSS branch. |
| `update/update` | `phi update` | `update_data` | Runtime migrated | Uses original update template with progress timeline, RKS graph, upstream-style long history limits, five-card row packing, randomized history title colors, Notes count, and today's task table before history rows. |
| `userinfo/userinfo`, `userinfo/userinfo-old` | `phi info`, `phi info1`, `phi info2` | `userinfo_data` | Runtime migrated | Uses original current/old userinfo templates with player data, stats, RKS/Data history, Limit-ACC RKS graph, and requested/background illustrations. |
| `chap/chap` | `phi chap` | `chap_data` | Runtime migrated | Uses original chap template with chapter song boxes, rating counts, average-ACC progress bars, and chapter/background illustrations inlined for remote t2i. |
| `historyB30/historyB30` | `phi hisb30` | `history_b30_data` | Runtime migrated | Uses original history B30 template with timeline rows, merged Phi/B27 enter/exit tags, player info, and base64 illustrations. |
| `analyzeSaveHistory/analyzeSaveHistory` | `phi 2025history`, `phi 年度总结` | `analyze_save_history_data` | Runtime migrated | Uses original yearly history template with upstream `stats` fields, top-3 rows, RKS/Data extrema, latest push times, AP days, and note totals from `notesInfo.json`. |
| `atlas/atlas` | `phi song` | `atlas_data` | Runtime migrated | Uses original atlas template with song metadata, illustration, per-chart note counts from `notesInfo.json`, and optional comment panel data. |
| `chartInfo/chartInfo` | `phi chart` | `chart_info_data` | Runtime migrated | Uses original chart info template with song/chart metadata, note counts and distribution from `notesInfo.json`, and online tag radar data. |
| `rand/rand` | `phi rand`, `phi random`, `phi 随机` | `rand_data` | Runtime migrated | Uses original random-song template with selected chart metadata, charter/illustrator fields, difficulty, rank, and base64 illustration. |
| `rankingList/rankingList`, `rankingList-old/rankingList` | `phi ranklist`, `phi 排行榜` | `ranking_list_data`, `ranking_list_old_data` | Runtime migrated | Default modern path uses original 2048x1080 ranking template; `ranklist_image_version=old` selects the legacy 800px list template with flattened B19 score chips. |
| `clg/clg` | `phi randclg` | `clg_data` | Runtime migrated | Uses original challenge template with selected chart illustrations, difficulty, total challenge value, and Tap/Drag/Hold/Flick/Combo counts from `notesInfo.json`. |
| `setting/userSetting` | `phi myset`, `phi mysetting`, `phi 用户设置`, `phi 个人设置` | `user_setting_data` | Runtime migrated | Uses original user-setting template with current values, option cards, selected markers, and random base64 background. |
| `ill/ill` | `phi ill`, `phi 曲绘` | `ill_data` | Runtime migrated | Uses original illustration template with base64 song art, illustrator label, and art-backed background. |
| `jrrp/jrrp` | `phi jrrp`, `phi 今日人品` | `jrrp_data` | Runtime migrated | Uses original daily-luck template with base64 background, luck rank, date, good/bad words, and sentence attribution. |
| `sign/sign` | `phi sign`, `phi task`, `phi retask` | `sign_data` | Runtime migrated | Uses original sign dashboard template for sign/task/retask image mode with player info, Notes, luck, tasks, calendar/notice, edge progress, and base64 task illustrations. |
| `newSong/newSong` | `phi newlog` | `newlog_data` | Runtime migrated | Uses original new-song update table with local new-song rows, difficulty and Tap/Drag/Hold/Flick/Combo note-count diffs, plus TapTap text sent after the image. |
| `guess/guess` | `phi guess`, `phi tipgame` final image hints | `guess_data` | Runtime migrated | Uses original guess template for cropped illustration hints and answer reveals; adapter keeps all images as data URIs and passes crop/reveal viewport sizes explicitly. |

## Converted But Not Yet Runtime-Migrated

These templates exist in `D:\astrbot_plugin_phi_plugin\jinja2`, but they are legacy, special-case, or future branches that are not selected by the current AstrBot command runtime.

| Template | Likely commands | Priority | Notes |
|---|---|---:|---|
| `chartImg/chartImg` | future `phi chart` preview branch | Medium | Converted and shares `chart_info_data`, but current command does not provide a chart preview image yet. |
| `setting/setting` | future admin settings | Low | Global setting command/template is converted but not implemented in AstrBot runtime yet. |
| `tasks/tasks` | legacy task panel variant | Low | Current upstream-style AstrBot runtime uses `sign/sign` for sign/task/retask; legacy `tasks/tasks` is converted but not selected. |
| `b19/b19666` | special B19/AP case | Low | Only needed if the special upstream condition is implemented. |

## Adapter Rules To Preserve

| Template | Adapter responsibility |
|---|---|
| `arcgrosB19/arcgrosB19` | Pre-format `song.std_score`. |
| `lvsco/lvsco` | Compute `rating_max` in Python. |
| `newnotice/newnotice` | Normalize notices and pre-format `notice.date_text`. |
| `b19/dss2` | Build `gameuser`, `BSIllPath`, `phi`, `b19_list`, and `spInfo` from records. |
| `list/list` | Build display rows with base64-capable illustration references, rating asset names, score, ACC, and suggestion text. |
| `suggest/suggest` | Group entries into `song[0]` through `song[5]` and normalize `phisong` rows. |
| `table/table` | Group charts by difficulty bucket, set `_imgPath`, and attach score overlays. |
| `score/score`, `score/scoreOld`, `score/scoreRankList` | Build iterable/attribute-compatible `scoreData`, top-level `EZ/HD/IN/AT` rows for the old layout, `history`, `ranklist`, AP/FC percentages, and global B30 Phi/Best position markers. |
| `update/update` | Build `box_line`, `rks_history`, `rks_range`, `added_rks_notes`, first-record/task rows, and scalar player/Notes fields. |
| `userinfo/userinfo`, `userinfo/userinfo-old` | Build `gameuser`, `userstats`, RKS/Data series, Limit-ACC RKS series, profile/background fields, and old/new layout shared data. |
| `chap/chap` | Build `player`, `count`, `song_box`, chapter illustration, and per-rank average-ACC `progress` from local catalog/save records. |
| `historyB30/historyB30` | Build player info, timeline `rows`, merged same-chart change tags, and background from historical B30 change records. |
| `analyzeSaveHistory/analyzeSaveHistory` | Build upstream `stats`, normalize Top3 rows for Jinja2, format RKS/Data deltas, and sum Tap/Drag/Hold/Flick/Combo/Time from `notesInfo.json` over score history events. |
| `atlas/atlas` | Build song metadata, chart rows, RGBA fallbacks, Tap/Drag/Hold/Flick/Combo from `notesInfo.json`, illustration/background data URIs, and normalized comment rows. |
| `chartInfo/chartInfo`, `chartImg/chartImg` | Build song/chart metadata, note counts, distribution rows, chart length, online tag `words`, `wordsMaxValue`, and illustration/background data URIs. |
| `rand/rand` | Build selected random chart metadata, difficulty label, rank, charter, illustrator, illustration, and background data URI. |
| `rankingList/rankingList`, `rankingList-old/rankingList` | Normalize online rank rows, selected player detail, RKS/Challenge history series, avatar/challenge fields, base64 backgrounds, B30 mini-card groups, and legacy flattened B19 score chips for the old template. |
| `clg/clg` | Build random challenge song rows, base64 chart illustrations, difficulty/rank labels, total challenge value, and Tap/Drag/Hold/Flick/Combo counts from `notesInfo.json`. |
| `setting/userSetting` | Build page metadata, setting groups, option cards, selected markers, and random base64 background. |
| `ill/ill` | Convert selected illustration to base64 data URI, attach illustrator text, and reuse illustration as background. |
| `jrrp/jrrp` | Normalize luck/date/sentence/good/bad fields, convert background to base64 data URI, and preserve 2048x1080 viewport. |
| `sign/sign` | Normalize player/Notes/luck/task/calendar/notice fields, edge progress defaults, avatar name, base64 background, and base64 task illustrations. |
| `newSong/newSong` | Build upstream `ans` table rows from version logs, normalize table cell spans/colors, keep template JS-free, and send local resources as inlined data URIs. |
| `guess/guess` | Normalize cropped illustration/reveal fields, base64 `illustration`/`ans`, filter CSS, crop coordinates, and `_viewport_width`/`_viewport_height` for t2i screenshots. |

Do not move these conversions back into command modules unless the command needs to choose a different template.

## Verification Commands

Run these after changing templates, adapters, or migrated command handlers:

```powershell
python -m py_compile phi_core\render\jinja_adapter.py phi_core\render\jinja_renderer.py phi_core\commands\_rendering.py
$env:PYTHONIOENCODING='utf-8'; python scripts\audit_jinja2_templates.py
$env:PYTHONIOENCODING='utf-8'; python scripts\smoke_jinja_render_chain.py
$env:PYTHONIOENCODING='utf-8'; python scripts\smoke_dispatch.py
```

Latest known verification:

- `scripts/audit_jinja2_templates.py`: `pass=36 review=0 fail=0`
- `scripts/smoke_jinja_render_chain.py`: passed
- `scripts/smoke_dispatch.py`: passed, including simulated transient t2i retry
- focused `chap/chap` self-contained render smoke: passed
- focused `historyB30/historyB30` self-contained render smoke: passed
- BOM check for touched files: no UTF-8 BOM detected

## Next Step

Continue with legacy/special variants only when their upstream runtime condition is implemented: `tasks/tasks`, `chartImg/chartImg`, `setting/setting`, and `b19/b19666`. `phi achievement` currently remains a port-specific list-style image because upstream has no dedicated `.art` template for it.
