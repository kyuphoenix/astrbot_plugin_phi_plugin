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
| `/score` | `phi score` | Partial | `html/score/score.art`, `scoreRankList.art` | Image mode now uses original score/userinfo resources with local score data and base64 assets. Still needs upstream `-dif`, `-or acc/score/fc/time`, `-unrank`, online ranklist, and score-history API parity. |
| `/suggest` | `phi suggest` | Partial | `html/suggest/suggest.art`, `suggest.css` | Image mode now uses original suggest resources with local target-ACC grouping. Still needs upstream filter parsing, average ACC/API data, AP/FC counts, and exact push-score algorithm parity. |
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
| `/rand` | `phi rand` | Partial | `html/rand/rand.art`, `rand.css` | Image mode now uses original random-song resources. Still needs upstream random filter parsing and exact chart selection behavior. |
| `/randclg` | `phi randclg` | Partial | `html/clg/clg.art`, `clg.css` | Image mode now uses original challenge resources with local random challenge selection. Still needs note breakdown and upstream range/rank parsing parity. |
| `/search` | `phi search` | Partial | Text in upstream | Implemented as text. Need verify BPM/difficulty/combo filter parity against upstream. |
| `/alias` | `phi alias` | Aligned | Text in upstream | Implemented as text. |
| `/setnick` | `phi setnick` | Partial | Admin text in upstream | Implemented. Need `delnick` command for full alias management parity. |
| `/delnick` | `phi delnick` | Partial | Admin text in upstream | Added deletion for AstrBot local custom aliases. Upstream route is commented out, so this intentionally only removes user-managed aliases, not bundled aliases. |
| `/com`, `/计算` | `phi com`, `phi 计算` | Aligned | Text in upstream | Implemented. |
| `/tips` | `phi tips` | Aligned | Text in upstream | Implemented. |
| `/newlog` | `phi newlog` | Partial | `html/newSong/newSong.art` | Current image path uses original resources but Python-built table. Need closer upstream new-song/update-log structure if desired. |
| `/newnotice` | `phi newnotice` | Partial | `html/newnotice/newnotice.art` | Current image path uses original resources but Python-built notice layout. Need direct original-template parity if desired. |
| `/live` | `phi live` | Partial | Text/API in upstream | Implemented. Need verify upstream API output formatting. |

## Binding, Login, And API Commands

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/bind`, `/cn bind`, `/gb bind` | `phi bind`, `phi cnbind`, `phi gbbind` | Partial | Text/QR in upstream | Implemented including TapTap QR login. Need compare final messages, default endpoint behavior, and auto-update details. |
| `/unbind` | `phi unbind` | Partial | Text in upstream | Implemented. Upstream has confirmation flow; current behavior should be checked. |
| `/clean` | `phi clean` | Partial | Text in upstream | Implemented. Need compare semantics with upstream clean. |
| `/sessionToken` | `phi sessiontoken`, `phi token`, `phi tk` | Partial | Text in upstream | Implemented with masking. Upstream also has `tk help`, currently missing. |
| `/tk help` | Missing | Missing | Help/document image/link | Need implement token help entry or remove from help until implemented. |
| `/auth` | `phi auth`, `phi login` | Partial | API binding text in upstream | Implemented. Need compare API token flow and error messages. |
| `/api help` | Missing | Missing | API help panel | Need implement or remove from help until implemented. |
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
| `/ranklist`, `/排行榜` | Missing | Missing | `html/rankingList/rankingList.art` | Need online ranking list API integration and renderer. |
| `/rankfind`, `/查询排名` | Missing | Missing | Ranking text/image | Need online ranking lookup implementation. |
| `/godlist`, `/封神榜` | Skipped | Skipped | Commented out upstream | Upstream route is commented out; no action unless explicitly requested. |

## Entertainment, Notes, And Settings

| Upstream command | Current AstrBot command | Status | Upstream template/resource | Notes / next action |
|---|---|---:|---|---|
| `/jrrp`, `/今日人品` | Missing | Missing | `html/jrrp/jrrp.art` | Need daily random/luck state and renderer. |
| `/guess` | Missing | Missing | `html/guess/guess.art` | Need game session state and answer handling. |
| `/tipgame` | Missing | Missing | Guess-game text/image | Need game session state and hint logic. |
| `/ltr` | Missing | Missing | Guess-letter game resources | Need game session state and reveal/open command handling. |
| `/tip`, `/ans`, `/open` | Missing | Missing | Guess-game support commands | Need integrate with active game sessions. |
| `/sign`, `/签到` | Missing | Missing | `html/sign/sign.art` | Need Notes economy and daily sign-in storage. |
| `/task`, `/我的任务` | Missing | Missing | `html/tasks/tasks.art` | Need task generation/storage and renderer. |
| `/retask`, `/刷新任务` | Missing | Missing | Text/tasks renderer | Need Notes cost and task refresh logic. |
| `/send`, `/送`, `/转` | Missing | Missing | Text in upstream | Need Notes transfer logic. |
| `/theme` | Missing | Missing | Text/config in upstream | Need user setting storage and render-theme integration. |
| `/myset`, `/用户设置`, `/个人设置` | Missing | Missing | `html/setting/userSetting.art` | Need user settings view/edit and renderer. |
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
