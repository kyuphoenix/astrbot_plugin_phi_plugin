# Phi Plugin Command Migration Status

This document tracks parity between the upstream `phi-plugin` commands and this AstrBot port. Update this table whenever a command is implemented, its logic is aligned, or its rendering is moved onto the original HTML/resource chain.

Status legend:

- `Aligned`: implemented and routed through the original-style HTML/resource chain where upstream uses an image template.
- `Partial`: implemented, but behavior, aliases, arguments, data source, or rendering still differs from upstream.
- `Text only`: implemented as text while upstream renders an image or richer output.
- `Missing`: not implemented in this AstrBot port yet.
- `Skipped`: intentionally not planned or not applicable to AstrBot.

## Core Query And Score Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/pgr`, `/rks`, `/bN` | `phi pgr`, `phi rks`, `phi b30`, `phi bN` | Partial | `html/b19/b19.art`, `html/b19/b19.css` | B30 image chain is aligned for `pgr/b30/rks`, and dynamic `bN` aliases from `b1` to `b100` now route through the shared B30 logic. User-specified background is not parsed yet. |
| `/p30`, `/x30`, `/fc30`, `/pN`, `/xN`, `/fcN` | `phi p30`, `phi x30`, `phi fc30`, `phi pN`, `phi xN`, `phi fcN` | Partial | `html/b19/dss2.art`, `html/b19/dss2.css` | Image chain now renders through converted Jinja2 `b19/dss2` with centralized adapter data, and dynamic aliases from `p1/x1/fc1` to `p100/x100/fc100` still route through the same command scripts. User-specified background and exact upstream title labels still need parity. |
| `/bestN` | `phi best [N]` | Partial | Upstream text/forward message / shared `html/b19/dss2.art` image path in AstrBot | Text mode remains implemented; image mode now uses converted Jinja2 `b19/dss2` through `dss2_record_list_data`. Decide whether to preserve AstrBot image behavior or match upstream text-only behavior. |
| `/lmtacc` | `phi lmtacc` | Partial | `html/b19/dss2.art`, `html/b19/dss2.css` | Image mode now uses converted Jinja2 `b19/dss2` through `dss2_record_list_data` with local minimum-ACC filtering. Needs closer upstream B19 exact layout and dynamic limit behavior. |
| `/score` | `phi score` | Partial | `html/score/score.art`, `scoreRankList.art` | Image mode now renders through converted Jinja2 `score/score` by default or `score/scoreOld` when `score_image_version=old`, with centralized `score_data`; parses upstream `-dif`, `-or acc/score/fc/time`, and `-unrank`, includes global B30 Phi/Best markers, local/remote score history rows, online score ranklist, and AP/FC count data when the API is available. Still needs exact upstream score-history API endpoint parity and broader live ranklist data checks. |
| `/suggest` | `phi suggest` | Partial | `html/suggest/suggest.art`, `suggest.css` | Image mode now uses original suggest resources, upstream-style定数/难度/评级筛选, next-RKS push-score calculation, per-group top-3 sorting with API average ACC when available, and the original phi/AP Count recommendation group. Still needs exact upstream wording/listScoreMaxNum behavior and broader live API data normalization checks. |
| `/chap` | `phi chap` | Partial | `html/chap/chap.art`, `chap.css`, `otherimg/chapHelp.png` | Image mode now returns upstream `chapHelp.png` for help and renders chapter summaries through converted Jinja2 `chap/chap` with upstream-style `song_box`, rating counts, and per-rank average-ACC progress bars. Exact upstream chapter alias/error wording still needs broader live parity checks. |
| `/achievement`, `/ahv` | `phi achievement`, `phi ahv` | Partial | Reuses `html/list/list.css` style output | Image mode still renders a port-specific original-resource list-style achievement panel because upstream has no dedicated `achievement.art`; `-v` reuses the historical `oldInfo/<version>/change.csv` table data like upstream. Still needs exact upstream achievement wording/layout parity if a source template appears later. |
| `/list` | `phi list` | Partial | `html/list/list.art`, `list.css` | Image mode now uses converted Jinja2 `list/list` with centralized row adapter data, respects a configurable `list_score_max_num` guard like upstream, and renders original-style request lines for difficulty/ACC. Still needs exact upstream filter grammar and full list row/data parity. |
| `/lvsco`, `/scolv` | `phi lvscore`, `phi lvsco`, `phi scolv` | Partial | `html/lvsco/lvsco.art`, `lvsco.css` | Image mode now uses original lvsco resources with local level summary stats. Still needs exact upstream range UI/data fields and full rank/difficulty filter parity. |
| `/info`, `/info1`, `/info2` | `phi info`, `phi info1`, `phi info2` | Partial | `html/userinfo/userinfo.art`, `userinfo.css`, `userinfo-old.css` | Image mode now renders through converted Jinja2 `userinfo/userinfo` and `userinfo/userinfo-old` with centralized `userinfo_data`, requested-song background support, player stats, RKS/Data history, and Limit-ACC RKS graph. Still needs broader live data parity checks against upstream API/history edge cases. |
| `/data` | `phi data` | Aligned | Text in upstream | Implemented as text, matching the lightweight nature of upstream data output. |
| `/update` | `phi update` | Partial | `html/update/update.art`, `update.css` | Image mode now renders through converted Jinja2 `update/update` with upstream-style long history display limits (10 days / 10 per day / 50 total by default), token/API remote history pull, original five-card row packing, randomized history title colors, Notes count, and today's task table before history rows. Still needs broader live parity checks for API/local fallback edge cases. |
| `/hisb30` | `phi hisb30` | Partial | `html/historyB30/historyB30.art`, `historyB30.css` | Image mode now renders through converted Jinja2 `historyB30/historyB30` with original timeline rows and merged same-chart Phi/B27 enter/exit tags. Still needs broader live parity checks for historical-constant caveats and random row color semantics. |
| `/2025history`, `/年度总结` | `phi 2025history`, `phi 年度总结` | Partial | `html/analyzeSaveHistory/analyzeSaveHistory.art`, `analyzeSaveHistory.css` | Image mode now renders through converted Jinja2 `analyzeSaveHistory/analyzeSaveHistory` with centralized `stats` adapter data, RKS/Data extrema, Top3 rows, latest push times, AP days, and note totals from `notesInfo.json`. Still needs broader live history edge-case comparison. |

## Song, Chart, And Catalog Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/song` | `phi song` | Partial | `html/atlas/atlas.art`, `atlas.css` | Image mode now renders through converted Jinja2 `atlas/atlas` with centralized `atlas_data`, base64 illustrations, per-chart Tap/Drag/Hold/Flick/Combo from `notesInfo.json`, and upstream `-comment` panel data. Still needs exact comments paging and broader live API field parity. |
| `/chart` | `phi chart` | Partial | `html/chartInfo/chartInfo.art`, `html/chartImg/chartImg.art` | Image mode now renders through converted Jinja2 `chartInfo/chartInfo` with centralized `chart_info_data`, base64 illustration, notes distribution from `notesInfo.json`, and online tag radar data. Full `chartImg/chartImg` preview image generation/download still needs parity. |
| `/tag` | `phi tag` | Partial | API/text in upstream chart module | Added read-only online chart tag lookup matching upstream command name. Need compare API permission messages and user-vote markers. |
| `/settag` | `phi settag` | Partial | API/text in upstream chart module | Added upstream command name with API tag-name lookup and numeric/name tag selection. Need compare exact permission/error wording. |
| `/cmt`, `/comment` | `phi cmt`, `phi comment` | Partial | Text/API in upstream | Implemented, but parsing/default rank and permission behavior may differ. Need compare with upstream. |
| `/mycmt` | `phi mycmt` | Partial | Text/API in upstream | Implemented, but output format and API error behavior need parity check. |
| `/recmt` | `phi recmt` | Partial | Text/API in upstream | Implemented, but upstream confirmation/permission flow may differ. |
| `/table` | `phi table` | Partial | `html/table/table.art`, `table.css` | Image mode now uses converted Jinja2 `table/table`, can overlay local player scores when a save is cached, and `-v` now reads historical `oldInfo/<version>/change.csv` data instead of the current catalog. Still needs exact upstream wording/error parity and broader version-table checks. |
| `/ill` | `phi ill` | Aligned | `html/ill/ill.art`, `ill.css` | Image mode now renders through converted Jinja2 `ill/ill` with centralized `ill_data`, base64 song art, illustrator label, and art-backed background. |
| `/rand` | `phi rand` | Partial | `html/rand/rand.art`, `rand.css` | Image mode now renders through converted Jinja2 `rand/rand` with centralized `rand_data`, and selects a random chart with upstream-style difficulty range plus EZ/HD/IN/AT filters. Exact upstream error wording and no-argument bulk behavior still need comparison. |
| `/randclg` | `phi randclg` | Partial | `html/clg/clg.art`, `clg.css` | Image mode now renders through converted Jinja2 `clg/clg` with centralized `clg_data`, base64 chart illustrations, and Tap/Drag/Hold/Flick/Combo note breakdown and supports upstream-style outer target/rank filters plus parenthesized per-chart filters. Exact random-search ordering and edge-case wording still need comparison. |
| `/search` | `phi search` | Partial | Text/forward message in upstream | Added upstream-style `bpm` / `difficulty|dif|定数|难度|定级` / `combo|cmb|物量|连击` filters with integer difficulty bucket behavior. Plain keyword fuzzy search remains as an AstrBot extension; upstream forward-message batching is not ported. |
| `/alias` | `phi alias` | Aligned | Text in upstream | Implemented as text. |
| `/setnick` | `phi setnick` | Partial | Admin text in upstream | Implemented. Need `delnick` command for full alias management parity. |
| `/delnick` | `phi delnick` | Partial | Admin text in upstream | Added deletion for AstrBot local custom aliases. Upstream route is commented out, so this intentionally only removes user-managed aliases, not bundled aliases. |
| `/com`, `/计算` | `phi com`, `phi 计算` | Aligned | Text in upstream | Implemented. |
| `/tips` | `phi tips` | Aligned | Text in upstream | Implemented. |
| `/newlog` | `phi newlog` | Partial | `html/newSong/newSong.art`, `newSong.css` | Now fetches TapTap official update text like upstream `PgrUpdateInfo`, sends image + update text in AstrBot runtime, and renders the original-style `newSong` table with new-song matching plus local difficulty and `tap/drag/hold/flick/combo` note-count diffs from `oldNotesInfo.json`. Still needs exact upstream runtime wording/error comparison. |
| `/newnotice` | `phi newnotice` | Partial | `html/newnotice/newnotice.art`, `newnotice.css` | Now prefers the upstream TapTap official notice API and renders through the original newnotice resource chain with remote images inlined as data URIs; falls back to local `notice.json` when TapTap is unavailable. Exact upstream runtime wording/error behavior still needs comparison. |
| `/live` | `phi live` | Aligned | Text/API in upstream | Calls the same `/live` API path, prefixes `直播速递：`, and uses the upstream empty/error wording. |

## Binding, Login, And API Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/bind`, `/cn bind`, `/gb bind` | `phi bind`, `phi cnbind`, `phi gbbind` | Partial | Text/QR in upstream | Implemented including TapTap QR login. Need compare final messages, default endpoint behavior, and auto-update details. |
| `/unbind` | `phi unbind` | Partial | Text in upstream | Implemented. Upstream has confirmation flow; current behavior should be checked. |
| `/clean` | `phi clean` | Partial | Text in upstream | Implemented. Need compare semantics with upstream clean. |
| `/sessionToken` | `phi sessiontoken`, `phi token`, `phi tk` | Partial | Text in upstream | Implemented with masking and text `tk help`; exact upstream wording still needs comparison. |
| `/tk help` | `phi tk help`, `phi token help` | Partial | Text in upstream/help docs | Implemented as text help through `sessiontoken.py`; exact upstream help image/link wording still needs comparison. |
| `/auth` | `phi auth`, `phi login` | Partial | API binding text in upstream | Implemented. Need compare API token flow and error messages. |
| `/api help` | `phi api help` | Partial | API help panel/text | Implemented as text help through `api.py`; admin API-management subcommands remain missing. |
| `/setApiToken` | `phi setapitoken` | Partial | API setting text | Added current-user API Token setup through `/setApiToken` using the bound sessionToken and upstream illegal-character guard. Need exact upstream casing/help wording comparison. |
| `/tkls`, `/lstk` | `phi tkls`, `phi lstk`, `phi tokenlist` | Partial | API setting text | Added current-user platform token list through `/token/list`, including current AstrBot platform marker. Need exact upstream formatting and permission wording comparison. |
| `/tokenManage`, `/tkManage` | Missing | Missing | API setting text | Token management command not ported. |
| `/clearApiData` | Missing | Missing | API setting text | API data cleanup command not ported. |
| `/updateHistory` | Missing | Missing | API setting text | API history sync command not ported. |
| `/updateUserToken` | Missing | Missing | API setting text | API user-token sync command not ported. |
| `/updateComment` | Missing | Missing | API setting text | API comment sync command not ported. |
| `/apiset` | Missing | Missing | API setting text | API setting command not ported. |

## Ranking And Online Features

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/ranklist`, `/排行榜` | `phi ranklist`, `phi 排行榜` | Partial | `html/rankingList/rankingList.art`, `html/rankingList-old/rankingList.art` | Image mode renders through converted Jinja2 `rankingList/rankingList` by default, or `rankingList-old/rankingList` when `ranklist_image_version=old`, with centralized adapters and base64 assets. Local Yunzai Redis fallback, exact permission wording, and deeper API field parity still need comparison. |
| `/rankfind`, `/查询排名` | `phi rankfind`, `phi 查询排名` | Partial | Ranking text/API | Added online `/get/ranklist/rksRank` lookup. Local Yunzai Redis fallback is intentionally not ported; exact API permission/error wording still needs comparison. |
| `/godlist`, `/封神榜` | Skipped | Skipped | Commented out upstream | Upstream route is commented out; no action unless explicitly requested. |

## Entertainment, Notes, And Settings

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/jrrp`, `/今日人品` | `phi jrrp`, `phi 今日人品` | Aligned | `html/jrrp/jrrp.art`, `jrrp.css` | Image mode now renders through converted Jinja2 `jrrp/jrrp` with centralized `jrrp_data`; daily luck keeps the same easing/word-pool structure, UTC+8 cache semantics, base64 background, luck/date fields, and sentence attribution. |
| `/guess` | `phi guess`, `phi 猜曲绘` | Partial | `html/guess/guess.art`, `guess.css` | Added session-scoped command-style guess-illustration game, weighted song selection, converted Jinja2 `guess/guess` CSS/SVG filter render, base64 illustrations, answer reveal, and `phi guess <answer>`. Upstream no-prefix answer listener, timed auto hints/timeout, recall behavior, and ban-group integration are still not ported. |
| `/tipgame` | `phi tipgame`, `phi 提示猜曲` | Partial | Guess-game text/image | Added session-scoped text-hint game with `phi tip` progression and final original guess-image hint. Still needs upstream cooldown/timeout automation and richer direct-message answer handling. |
| `/ltr` | `phi ltr`, `phi letter`, `phi 开字母` | Partial | Guess-letter text/markdown output | Added session-scoped letter game, weighted multi-song selection, `phi ltr n1 <answer>`, `phi open <letter>`, random `phi tip`, answer reveal, and optional `pypinyin` initials matching. Still text-only and does not yet reproduce upstream QQ markdown buttons/cooldowns/timeout. |
| `/tip`, `/ans`, `/open` | `phi tip`, `phi ans`, `phi open` | Partial | Guess-game support commands | Integrated with active session state for guess, tipgame, and letter games. Direct `/open X` without the `phi` command group is intentionally not implemented yet in this AstrBot command-style pass. |
| `/sign`, `/签到`, `/打卡` | `phi sign`, `phi 签到`, `phi 打卡` | Partial | `html/sign/sign.art`, `sign.css` | Image mode now renders through converted Jinja2 `sign/sign` with centralized `sign_data`; AstrBot Notes storage, daily reward/history, calendar, jrrp reuse, task preview, edge progress, and base64 task illustrations are preserved. Needs exact notice/theme parity and broader live runtime testing. |
| `/task`, `/我的任务` | `phi task`, `phi tasks`, `phi 我的任务` | Partial | Upstream currently renders through `html/sign/sign.art`; legacy `html/tasks/tasks.art` exists | Image mode now renders through converted Jinja2 `sign/sign` via `sign_data`, matching the current sign-dashboard route. API-average task generation is best-effort with local fallback. |
| `/retask`, `/刷新任务` | `phi retask`, `phi 刷新任务` | Partial | Upstream currently renders through `html/sign/sign.art`; legacy `html/tasks/tasks.art` exists | Image mode now renders through converted Jinja2 `sign/sign` via `sign_data`, preserving daily free refresh, 20 Notes paid refresh, and preserve-finished behavior. Needs exact upstream edge-case wording. |
| `/send`, `/送`, `/转` | `phi send`, `phi 送`, `phi 转` | Partial | Text in upstream | Added local Notes transfer with upstream 80% recipient amount and self-transfer joke penalty. AstrBot command layer does not validate group member existence yet. |
| `/theme` | `phi theme` | Partial | Text/config in upstream | Added user theme persistence. Rendered templates still mostly use default theme until per-user theme application is wired broadly. |
| `/myset`, `/用户设置`, `/个人设置` | `phi myset`, `phi 用户设置`, `phi 个人设置` | Partial | `html/setting/userSetting.art`, `userSetting.css` | Image mode now renders through converted Jinja2 `setting/userSetting` with centralized `user_setting_data`, current values, option cards, selected markers, and base64 assets. Need exact upstream option list and global setting command parity. |
| `/set` | Missing | Missing | `html/setting/setting.art` | Admin/global setting management not ported. |

## Admin And Maintenance Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/backup` | Missing | Missing | File management | Need decide whether AstrBot data backup should be implemented. |
| `/restore` | Missing | Missing | File management | Risky; needs explicit design before implementation. |
| `/repu` | Skipped | Skipped | Puppeteer restart | Not applicable to remote AstrBot t2i path unless a local browser renderer is added. |
| `/get` | Missing | Missing | Admin ranking token lookup | Sensitive admin command; needs explicit design. |
| `/del` | Missing | Missing | Admin token ban | Sensitive admin command; needs explicit design. |
| `/allow` | Missing | Missing | Admin token allow | Sensitive admin command; needs explicit design. |
| `/ban` | Missing | Missing | Feature ban management | Current AstrBot permission/config model differs; needs design. |
| `/unban` | Missing | Missing | Feature ban management | Current AstrBot permission/config model differs; needs design. |
| `/下载曲绘`, `/down ill` | `phi down ill`, `phi 下载曲绘` | Aligned | Resource downloader | Implemented for AstrBot downloads resource layout. |
| `/更新`, `/gx` | Missing | Missing | Plugin self-update | Upstream self-update does not map cleanly to AstrBot plugin deployment. Need decide whether to skip. |

## Renderer Parity Notes

| Area | Current state | Next action |
|---|---|---|
| Runtime resources | `downloads/html` is downloaded from `kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template`; `downloads/info` and `downloads/otherill` remain from `Catrong/phi-plugin`; `downloads/original_ill` remains from `Catrong/phi-plugin-ill` | Keep all t2i-bound resources converted to `data:*;base64,...`. |
| Direct `.art` rendering | Not implemented. Converted Jinja2 templates now cover B30, dss2 record lists, list/suggest/table/lvsco/newnotice/help, score, update, userinfo, chap, historyB30, analyzeSaveHistory, atlas, chartInfo, and rand. `original.py` still builds Python HTML for commands not yet migrated. | Continue moving remaining medium-priority ranking templates to `render_jinja_template(...)`. |
| Text fallback image panel | Still exists for commands not yet migrated, but core query/stat commands now return command-specific images in image mode. | Continue replacing remaining text panels with original command-specific templates. |
| Help panel accuracy | Uses upstream `help.json`, so it lists commands not yet implemented. | Either keep this tracker as source of truth during migration or filter help entries until commands are implemented. |

## Update Rule

When a command is completed, update the relevant row:

1. Set `Status` to `Aligned` only after behavior and rendering have both been checked against upstream.
2. Set `Status` to `Partial` when command exists but aliases, arguments, data, or rendering still differ.
3. Add a short note describing what changed and what remains.
4. Run smoke checks and update `docs/jinja2-migration-list.md` if the shared Jinja2 rendering chain changes.
