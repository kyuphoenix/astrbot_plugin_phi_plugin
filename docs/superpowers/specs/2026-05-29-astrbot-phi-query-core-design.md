# AstrBot Phi Plugin Query Core Refactor Design

Date: 2026-05-29

## Goal

Refactor `D:\astrbot_plugin_phi_plugin\phi-plugin` into a native AstrBot Python plugin in `D:\astrbot_plugin_phi_plugin\astrbot_plugin_phi_plugin`, using `D:\astrbot_plugin_pjsk_stickers\astrbot_plugin_meme_stickers` as the structural example and `D:\astrbot_plugin_pjsk_stickers\AstrBot插件开发指南.md` as the framework reference.

The first implementation target is the query core version: a usable AstrBot plugin that supports Phigros song lookup and the core save/query workflow without depending on Yunzai, Node.js, global `redis`, or Yunzai message objects.

## Source Context

The original `phi-plugin` is a Yunzai-style Node.js plugin:

- `index.js` initializes song data and dynamically loads `apps/*.js`.
- `apps/session.js` handles bind, update, unbind, clean, and session token lookup.
- `apps/user.js` handles data, info, lvscore, list, history summary, and historical b30.
- `apps/b19.js` handles b30/rks, p/x/fc variants, best, score, suggestions, chapters, and achievements.
- `apps/phisong.js` handles song atlas, search, aliases, illustrations, random songs, tips, new logs, table, comments, and tags.
- Rendering flows through `model/picmodle.js`, HTML `.art` templates, and Puppeteer.
- Persistent data paths are rooted under `plugins/phi-plugin/data` and config paths under `plugins/phi-plugin/config`.
- Several modules assume Yunzai globals or libraries: `plugin`, `e.reply`, `segment`, `common`, `redis`, `Bot`, and Puppeteer renderer classes.

The AstrBot example plugin uses:

- `main.py` as the AstrBot entrypoint.
- `metadata.yaml`, `_conf_schema.json`, and `requirements.txt` at the plugin root.
- A dedicated Python package for reusable business logic.
- `StarTools.get_data_dir()` for plugin data.
- `@filter.command(...)` and `@filter.event_message_type(...)` decorators for event handling.
- `event.plain_result(...)`, `event.image_result(...)`, and message components for output.

## Scope

### In Scope For Query Core Version

Implement these commands with AstrBot-native handlers:

- `/phi help`: show supported AstrBot version commands and feature status.
- `/phi song <query>`: show song metadata and chart constants from local resources.
- `/phi search <query>`: fuzzy search songs and aliases.
- `/phi rand`: choose a random song, optionally including difficulty information.
- `/phi ill <query>`: send a local illustration when available; otherwise return a useful missing-resource message.
- `/phi bind <sessionToken>`: bind a Phigros session token for the sender.
- `/phi unbind`: remove the sender's token and local save cache.
- `/phi clean`: remove all local plugin data for the sender.
- `/phi update`: fetch and cache the sender's cloud save.
- `/phi b30` and `/phi rks`: show best-30/rks summary from cached or freshly fetched save data.
- `/phi score <query>`: show the sender's score for one song.
- `/phi info`: show a compact user statistics summary.

### Explicitly Out Of Scope For First Version

Do not migrate these in the first implementation pass:

- Sign-in, tasks, currency, and themes from `apps/money.js`.
- Guess games from `apps/guessGame.js`.
- Global ranklist and rank finding from `apps/RankList.js`.
- Comment, chart tag, and voting features.
- Admin/manage commands, backup/restore, plugin self-update, and illustration repository update.
- Full HTML/Puppeteer image rendering parity.
- Yunzai compatibility or Node.js subprocess bridge.
- Redis-backed cross-instance state.

Unsupported commands should fail gracefully with a clear message when referenced from help or command parsing.

## Architecture

The refactor should use a native Python package beside `main.py`:

```text
astrbot_plugin_phi_plugin/
├── main.py
├── metadata.yaml
├── _conf_schema.json
├── requirements.txt
├── README.md
├── phi_core/
│   ├── __init__.py
│   ├── config.py
│   ├── paths.py
│   ├── models.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── search.py
│   ├── save/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── codec.py
│   │   └── store.py
│   ├── query/
│   │   ├── __init__.py
│   │   ├── b30.py
│   │   ├── score.py
│   │   └── user_info.py
│   └── render/
│       ├── __init__.py
│       └── text.py
└── resources/
    └── info/...
```

`main.py` should stay thin. It should parse AstrBot events, normalize the command text, call `phi_core` services, and yield AstrBot results.

`phi_core` should contain framework-independent Python code so the core can be tested without AstrBot.

## Data And Resources

The initial plugin should copy or reuse the original static resources needed for lookup:

- `resources/info/info.csv`
- `resources/info/difficulty.csv`
- `resources/info/infolist.json`
- `resources/info/nicklist.yaml`
- `resources/info/chaplist.yaml`
- `resources/info/tips.yaml`
- `resources/info/notesInfo.json`
- `resources/info/oldNotesInfo.json` if needed for metadata compatibility
- `resources/info/DLC/*.json`
- `resources/info/spinfo.json`
- `resources/otherill/*` if bundled illustration fallback is useful

Large downloaded illustration folders such as `original_ill` should not be required for initial load. The plugin should support them if present under the plugin resource directory, but should not fail when they are absent.

Runtime data must be stored under `StarTools.get_data_dir("astrbot_plugin_phi_plugin")`, not under the original Yunzai `plugins/phi-plugin/data` path.

## Save Workflow

The save workflow should be isolated behind `phi_core.save`:

- `store.py` stores per-user binding and cached save JSON under the AstrBot data directory.
- `client.py` performs async HTTP requests with `httpx` and a configurable timeout.
- `codec.py` parses/decrypts Phigros save payloads. If the full original cloud-save protocol cannot be completed in one pass, preserve a narrow interface and return a clear `SaveNotAvailable` error from command handlers.

Command behavior:

- `/phi bind <sessionToken>` validates non-empty input and saves the token.
- `/phi update` requires a bound token, fetches the save, parses it, stores a normalized save snapshot, and returns a short update summary.
- `/phi b30`, `/phi rks`, `/phi score`, and `/phi info` use cached save data first. If the cache is missing, tell the user to run `/phi update`.

## Query Logic

Song lookup should be implemented before save-dependent commands:

- Load songs into typed dataclasses or Pydantic-style models.
- Normalize ids with the original `.0` convention where needed.
- Include aliases from `nicklist.yaml`.
- Use a deterministic fuzzy search strategy based on exact id/name/alias first, then approximate matching.
- Avoid hidden global mutable state except a plugin-level loaded catalog service.

B30/rks logic should be a Python port of the original formula and record sorting, but only for the standard best-30 query in the first pass. Variants such as `x30`, `fc30`, `best n`, suggestion lists, and chapter reports are later work.

## Rendering

First version rendering should be text-first:

- Return readable plain-text summaries for help, song, search, rand, b30/rks, score, and info.
- Use local image sending only for `/phi ill` when a file exists.
- Define a render module boundary so future versions can add PIL or browser-rendered images without changing command handlers.

This reduces migration risk because the original Puppeteer stack depends heavily on Yunzai renderer classes and `.art` templates.

## AstrBot Integration

`metadata.yaml` should define the plugin metadata instead of using deprecated register decorators.

`_conf_schema.json` should include:

- `cmdhead`: string, default `phi`.
- `default_global`: bool, default `false`.
- `render_mode`: string, default `text`, options `text` and `image` with image treated as future-compatible.
- `max_b30`: int, default `30`, bounded to a practical range.
- `api_base_url`: string, default copied from the original constant.
- `request_timeout`: int, default `10`.
- `github_proxy`: string, default empty.

`requirements.txt` should include only Python dependencies actually used in the first version, likely:

- `httpx`
- `PyYAML`
- `pydantic` only if models use it

## Error Handling

Handlers should return user-readable errors for expected issues:

- Missing command arguments.
- No matching song.
- Multiple likely song matches.
- Missing bound session token.
- Missing cached save.
- Cloud save/API request failure.
- Unsupported migrated-later command.

Errors should not expose session tokens or full stack traces in chat. Internal details can be logged with AstrBot logger.

## Testing And Verification

Core code should be testable without AstrBot:

- Static data loader can read bundled resources.
- Song lookup handles exact title, id, and alias.
- Random selection returns a valid song.
- B30 calculation sorts and caps records correctly from fixture save data.
- Store reads/writes per-user binding and cache data.

Minimum runtime checks:

- `python -m compileall .`
- Import `phi_core` modules without AstrBot if possible.
- Run targeted unit tests if a test suite is added.

## Acceptance Criteria

The refactor is acceptable when:

- The target directory is a valid AstrBot plugin layout.
- The plugin no longer requires Node.js/Yunzai at runtime.
- AstrBot can import `main.py` without missing local package errors.
- Offline commands `/phi help`, `/phi song`, `/phi search`, `/phi rand`, and `/phi ill` work against local resources.
- Save commands implement a clear bind/update/query flow or return explicit, user-safe not-yet-available errors at the save client boundary if the cloud protocol needs another pass.
- Unsupported first-pass features are documented and do not crash the plugin.
