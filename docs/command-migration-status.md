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
| `/pgr`, `/rks`, `/bN` | `phi pgr`, `phi rks`, `phi b30` | Partial | `html/b19/b19.art`, `html/b19/b19.css` | B30 image chain is aligned for `pgr/b30/rks`, but dynamic `bN` aliases such as `b60` are not registered yet. User-specified background is not parsed yet. |
| `/p30`, `/x30`, `/fc30`, `/pN`, `/xN`, `/fcN` | `phi p30`, `phi x30`, `phi fc30` | Partial | `html/b19/dss2.art`, `html/b19/dss2.css` | Image chain uses original-style `dss2` resources. Dynamic command aliases and user-specified background still need parity. |
| `/bestN` | `phi best [N]` | Partial | Upstream text/forward message | Implemented; currently can render image in image mode through `record_list_html`, while upstream treats `best` as text/forward-message. Decide whether to preserve AstrBot image behavior or match upstream text-only behavior. |
| `/lmtacc` | `phi lmtacc` | Partial | `html/b19/dss2.css` / B30-style output | Now renders through the shared original HTML/resource chain in image mode using the local minimum-ACC filter. Needs closer upstream B19 exact layout and dynamic limit behavior. |
| `/score` | `phi score` | Partial | `html/score/score.art`, `scoreRankList.art` | Image mode uses original score/userinfo resources, parses upstream `-dif`, `-or acc/score/fc/time`, and `-unrank`, and can render online score ranklist plus AP/FC count data when the API is available. Still needs exact score-history API parity and closer original ranklist styling/data normalization. |
| `/suggest` | `phi suggest` | Partial | `html/suggest/suggest.art`, `suggest.css` | Image mode now uses original suggest resources, upstream-style定数/难度/评级筛选, next-RKS push-score calculation, per-group top-3 sorting with API average ACC when available, and the original phi/AP Count recommendation group. Still needs exact upstream wording/listScoreMaxNum behavior and broader live API data normalization checks. |
| `/chap` | `phi chap` | Partial | `html/chap/chap.art`, `chap.css`, `otherimg/chapHelp.png` | Image mode now returns upstream `chapHelp.png` for help and renders chapter summaries through original chap resources. Layout/data are still adapted from local summary logic rather than direct upstream `song_box` parity. |
| `/achievement`, `/ahv` | `phi achievement`, `phi ahv` | Partial | Reuses `html/list/list.css` style output | Image mode now renders an original-resource list-style achievement panel. Still needs upstream `-v` version support and exact original achievement/table behavior. |
| `/list` | `phi list` | Partial | `html/list/list.art`, `list.css` | Image mode now uses original list resources and existing local filter parser. Still needs exact upstream filter grammar and list size/config parity. |
| `/lvsco`, `/scolv` | `phi lvscore`, `phi lvsco`, `phi scolv` | Partial | `html/lvsco/lvsco.art`, `lvsco.css` | Image mode now uses original lvsco resources with local level summary stats. Still needs exact upstream range UI/data fields and full rank/difficulty filter parity. |
| `/info` | `phi info` | Partial | `html/userinfo/userinfo.art`, `userinfo.css` | Image chain uses original resources. Need user-selected background parsing, info variant handling (`info1/info2`), and closer data parity. |
| `/data` | `phi data` | Aligned | Text in upstream | Implemented as text, matching the lightweight nature of upstream data output. |
| `/update` | `phi update` | Partial | `html/update/update.art`, `update.css` | Image chain uses original resources. Need closer task data, timeline grouping, and any remaining original progress details. |
| `/hisb30` | `phi hisb30` | Partial | `html/historyB30/historyB30.art`, `historyB30.css` | Image mode now renders history B30 changes through original history resources. Still needs upstream exact rows/color semantics and historical-constant caveats. |
| `/2025history`, `/年度总结` | `phi 2025history`, `phi 年度总结` | Partial | `html/analyzeSaveHistory/analyzeSaveHistory.art`, `analyzeSaveHistory.css` | Image mode now renders local history analysis through original analyzeSaveHistory resources. Still needs exact upstream stat fields/note-count details. |

## Song, Chart, And Catalog Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/song` | `phi song` | Partial | `html/atlas/atlas.art`, `atlas.css` | Image mode now uses original atlas resources for song details with base64 illustrations. Still needs comments option and exact chart/note-field parity. |
| `/chart` | `phi chart` | Partial | `html/chartInfo/chartInfo.art`, `html/chartImg/chartImg.art` | Added original-resource chart info render with base64 illustration, notes distribution, and online tag data. Full chart preview image generation/download still needs parity. |
| `/tag` | `phi tag` | Partial | API/text in upstream chart module | Added read-only online chart tag lookup matching upstream command name. Need compare API permission messages and user-vote markers. |
| `/settag` | `phi settag` | Partial | API/text in upstream chart module | Added upstream command name with API tag-name lookup and numeric/name tag selection. Need compare exact permission/error wording. |
| `/cmt`, `/comment` | `phi cmt`, `phi comment` | Partial | Text/API in upstream | Implemented, but parsing/default rank and permission behavior may differ. Need compare with upstream. |
| `/mycmt` | `phi mycmt` | Partial | Text/API in upstream | Implemented, but output format and API error behavior need parity check. |
| `/recmt` | `phi recmt` | Partial | Text/API in upstream | Implemented, but upstream confirmation/permission flow may differ. |
| `/table` | `phi table` | Partial | `html/table/table.art`, `table.css` | Image mode now uses original table resources and can overlay local player scores when a save is cached. Still needs full upstream version table parity. |
| `/ill` | `phi ill` | Aligned | `html/ill/ill.art`, `ill.css` | Uses original-style HTML chain with base64 image transfer. |
| `/rand` | `phi rand` | Partial | `html/rand/rand.art`, `rand.css` | Image mode uses original random-song resources and now selects a random chart with upstream-style difficulty range plus EZ/HD/IN/AT filters. Exact upstream error wording and no-argument bulk behavior still need comparison. |
| `/randclg` | `phi randclg` | Partial | `html/clg/clg.art`, `clg.css` | Image mode uses original challenge resources, now renders Tap/Drag/Hold/Flick/Combo note breakdown and supports upstream-style outer target/rank filters plus parenthesized per-chart filters. Exact random-search ordering and edge-case wording still need comparison. |
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
| `/setApiToken` | Missing | Missing | API setting text | Admin/API management command not ported. |
| `/tkls`, `/lstk` | Missing | Missing | API setting text | Token list command not ported. |
| `/tokenManage`, `/tkManage` | Missing | Missing | API setting text | Token management command not ported. |
| `/clearApiData` | Missing | Missing | API setting text | API data cleanup command not ported. |
| `/updateHistory` | Missing | Missing | API setting text | API history sync command not ported. |
| `/updateUserToken` | Missing | Missing | API setting text | API user-token sync command not ported. |
| `/updateComment` | Missing | Missing | API setting text | API comment sync command not ported. |
| `/apiset` | Missing | Missing | API setting text | API setting command not ported. |

## Ranking And Online Features

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/ranklist`, `/排行榜` | `phi ranklist`, `phi 排行榜` | Partial | `html/rankingList/rankingList.art`, `rankingList.css` | Added online API integration and original-resource image chain with base64 assets. Local Yunzai Redis fallback, exact permission wording, and deeper API field parity still need comparison. |
| `/rankfind`, `/查询排名` | `phi rankfind`, `phi 查询排名` | Partial | Ranking text/API | Added online `/get/ranklist/rksRank` lookup. Local Yunzai Redis fallback is intentionally not ported; exact API permission/error wording still needs comparison. |
| `/godlist`, `/封神榜` | Skipped | Skipped | Commented out upstream | Upstream route is commented out; no action unless explicitly requested. |

## Entertainment, Notes, And Settings

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/jrrp`, `/今日人品` | `phi jrrp`, `phi 今日人品` | Aligned | `html/jrrp/jrrp.art`, `jrrp.css` | Audited against upstream `apps/jrrp.js`: daily luck uses the same easing/word-pool structure, UTC+8 day cache semantics, fixed `ShineAfter` background, and original jrrp resources/base64 assets. |
| `/guess` | `phi guess`, `phi 猜曲绘` | Partial | `html/guess/guess.art`, `guess.css` | Added session-scoped command-style guess-illustration game, weighted song selection, original guess CSS/SVG filter render, base64 illustrations, answer reveal, and `phi guess <answer>`. Upstream no-prefix answer listener, timed auto hints/timeout, recall behavior, and ban-group integration are still not ported. |
| `/tipgame` | `phi tipgame`, `phi 提示猜曲` | Partial | Guess-game text/image | Added session-scoped text-hint game with `phi tip` progression and final original guess-image hint. Still needs upstream cooldown/timeout automation and richer direct-message answer handling. |
| `/ltr` | `phi ltr`, `phi letter`, `phi 开字母` | Partial | Guess-letter text/markdown output | Added session-scoped letter game, weighted multi-song selection, `phi ltr n1 <answer>`, `phi open <letter>`, random `phi tip`, answer reveal, and optional `pypinyin` initials matching. Still text-only and does not yet reproduce upstream QQ markdown buttons/cooldowns/timeout. |
| `/tip`, `/ans`, `/open` | `phi tip`, `phi ans`, `phi open` | Partial | Guess-game support commands | Integrated with active session state for guess, tipgame, and letter games. Direct `/open X` without the `phi` command group is intentionally not implemented yet in this AstrBot command-style pass. |
| `/sign`, `/签到`, `/打卡` | `phi sign`, `phi 签到`, `phi 打卡` | Partial | `html/sign/sign.art`, `sign.css` | Added AstrBot Notes storage, daily reward/history, calendar, jrrp reuse, task preview, and original sign resource chain. Needs exact notice/theme parity and broader runtime testing. |
| `/task`, `/我的任务` | `phi task`, `phi tasks`, `phi 我的任务` | Partial | Upstream currently renders through `html/sign/sign.art`; legacy `html/tasks/tasks.art` exists | Added task generation/storage and image mode reuses sign dashboard like current upstream `money.js`. API-average task generation is best-effort with local fallback. |
| `/retask`, `/刷新任务` | `phi retask`, `phi 刷新任务` | Partial | Upstream currently renders through `html/sign/sign.art`; legacy `html/tasks/tasks.art` exists | Added daily free refresh, 20 Notes paid refresh, preserve-finished behavior, and sign-dashboard render. Needs exact upstream edge-case wording. |
| `/send`, `/送`, `/转` | `phi send`, `phi 送`, `phi 转` | Partial | Text in upstream | Added local Notes transfer with upstream 80% recipient amount and self-transfer joke penalty. AstrBot command layer does not validate group member existence yet. |
| `/theme` | `phi theme` | Partial | Text/config in upstream | Added user theme persistence. Rendered templates still mostly use default theme until per-user theme application is wired broadly. |
| `/myset`, `/用户设置`, `/个人设置` | `phi myset`, `phi 用户设置`, `phi 个人设置` | Partial | `html/setting/userSetting.art`, `userSetting.css` | Added setting view/update and image mode uses original setting resources/base64 assets. Need exact upstream option list and global setting command parity. |
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
| Original HTML assets | Downloaded into AstrBot data `downloads/html`, `downloads/info`, `downloads/otherill`, `downloads/original_ill` | Keep all t2i-bound resources converted to `data:*;base64,...`. |
| Direct `.art` rendering | Not implemented. Current `original.py` builds Python HTML using original CSS/classes/assets for more command templates. | For stronger parity, add a small `.art` render/translation layer or continue porting each template structure carefully. |
| Text fallback image panel | Still exists for commands not yet migrated, but core query/stat commands now return command-specific images in image mode. | Continue replacing remaining text panels with original command-specific templates. |
| Help panel accuracy | Uses upstream `help.json`, so it lists commands not yet implemented. | Either keep this tracker as source of truth during migration or filter help entries until commands are implemented. |

## Update Rule

When a command is completed, update the relevant row:

1. Set `Status` to `Aligned` only after behavior and rendering have both been checked against upstream.
2. Set `Status` to `Partial` when command exists but aliases, arguments, data, or rendering still differ.
3. Add a short note describing what changed and what remains.
4. Run smoke checks and update `docs/pgr-render-chain.md` if the shared rendering chain changes.
