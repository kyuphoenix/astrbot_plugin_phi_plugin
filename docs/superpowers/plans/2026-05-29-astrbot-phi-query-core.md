# AstrBot Phi Query Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native AstrBot Python plugin for the query-core subset of phi-plugin.

**Architecture:** `main.py` exposes AstrBot command handlers while `phi_core` holds framework-independent data loading, search, persistence, save-client boundaries, query calculation, and text rendering. Static song resources are copied from the original plugin; runtime user data is stored under `StarTools.get_data_dir("astrbot_plugin_phi_plugin")`.

**Tech Stack:** Python 3, AstrBot plugin API, `httpx`, `PyYAML`, standard-library `csv/json/difflib/pathlib/dataclasses`, optional local resource files from original `phi-plugin`.

---

## File Structure

- Create `main.py`: AstrBot entrypoint with command handlers for help/song/search/rand/ill/bind/unbind/clean/update/b30/rks/score/info.
- Create `metadata.yaml`: AstrBot plugin metadata.
- Create `_conf_schema.json`: AstrBot configuration schema.
- Create `requirements.txt`: Python runtime dependencies.
- Create `README.md`: supported commands and migration status.
- Create `phi_core/config.py`: typed runtime settings from AstrBot config.
- Create `phi_core/paths.py`: resource and data directory helpers.
- Create `phi_core/models.py`: dataclasses for songs, charts, save records, and query results.
- Create `phi_core/data/loader.py`: static resource loading from CSV/JSON/YAML.
- Create `phi_core/data/search.py`: exact and fuzzy song lookup.
- Create `phi_core/save/store.py`: per-user token and save cache storage.
- Create `phi_core/save/client.py`: async API/save fetch boundary.
- Create `phi_core/save/codec.py`: normalized save parsing and clear not-available errors for unsupported raw protocols.
- Create `phi_core/query/b30.py`: best-30/rks calculation from normalized cached saves.
- Create `phi_core/query/score.py`: per-song score lookup.
- Create `phi_core/query/user_info.py`: compact user summary.
- Create `phi_core/render/text.py`: text formatting for all first-pass responses.
- Copy resource files under `resources/info` and `resources/otherill` from the original plugin.

## Task 1: Plugin Skeleton

**Files:**
- Create: `metadata.yaml`
- Create: `_conf_schema.json`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `phi_core/__init__.py`

- [ ] **Step 1: Create metadata**

```yaml
name: astrbot_plugin_phi_plugin
display_name: Phi Plugin Query Core
desc: AstrBot native Phigros query-core plugin refactored from phi-plugin
version: v0.1.0
author: Catrong, AstrBot refactor
repo: "无"
support_platforms:
  - aiocqhttp
```

- [ ] **Step 2: Create configuration schema**

```json
{
  "cmdhead": {
    "description": "命令头，不包含 / 或 #",
    "type": "string",
    "default": "phi"
  },
  "default_global": {
    "description": "默认使用国际服存档接口",
    "type": "bool",
    "default": false
  },
  "render_mode": {
    "description": "渲染模式；当前版本 text 可用，image 为后续预留",
    "type": "string",
    "default": "text",
    "options": ["text", "image"]
  },
  "max_b30": {
    "description": "B30 展示条数",
    "type": "int",
    "default": 30,
    "slider": {"min": 1, "max": 50, "step": 1}
  },
  "api_base_url": {
    "description": "Phi Plugin 联合查分 API 地址",
    "type": "string",
    "default": "https://phib19.top:8080"
  },
  "request_timeout": {
    "description": "网络请求超时时间（秒）",
    "type": "int",
    "default": 10,
    "slider": {"min": 3, "max": 60, "step": 1}
  },
  "github_proxy": {
    "description": "GitHub 代理地址，当前仅预留",
    "type": "string",
    "default": ""
  }
}
```

- [ ] **Step 3: Create requirements**

```text
httpx
PyYAML
```

- [ ] **Step 4: Create README with command list and migration status**

- [ ] **Step 5: Commit skeleton**

```bash
git add metadata.yaml _conf_schema.json requirements.txt README.md phi_core/__init__.py
git commit -m "feat: add AstrBot plugin skeleton"
```

## Task 2: Static Resources And Data Loader

**Files:**
- Copy: `resources/info/*` from original plugin, excluding very large nonessential folders if needed.
- Copy: `resources/otherill/*`
- Create: `phi_core/models.py`
- Create: `phi_core/paths.py`
- Create: `phi_core/config.py`
- Create: `phi_core/data/__init__.py`
- Create: `phi_core/data/loader.py`
- Create: `phi_core/data/search.py`

- [ ] **Step 1: Copy resource files from original plugin**

Run PowerShell copy commands preserving folder structure.

- [ ] **Step 2: Define dataclasses**

Create `SongChart`, `Song`, `ScoreRecord`, `SaveSnapshot`, `Best30Result`, and `UserSummary` dataclasses.

- [ ] **Step 3: Implement paths/config helpers**

`PluginConfig.from_astrbot(config)` should read defaults safely from dict-like AstrBot config.

- [ ] **Step 4: Implement resource loader**

Load `info.csv`, `difficulty.csv`, `infolist.json`, `nicklist.yaml`, DLC JSON, and SP info into a `SongCatalog`.

- [ ] **Step 5: Implement exact and fuzzy search**

Exact id/name/alias matches come first, then `difflib.SequenceMatcher` fuzzy results.

- [ ] **Step 6: Verify loader**

Run: `python -m compileall phi_core`
Expected: success.

- [ ] **Step 7: Commit data layer**

```bash
git add resources phi_core
git commit -m "feat: add phi static data loader"
```

## Task 3: Text Rendering And Offline Commands

**Files:**
- Create: `phi_core/render/__init__.py`
- Create: `phi_core/render/text.py`
- Create: `main.py`

- [ ] **Step 1: Implement text renderers**

Render help, song detail, search results, random song, missing illustration, unsupported command, b30, score, and info summaries.

- [ ] **Step 2: Implement AstrBot class and offline commands**

Use `@filter.command("phi")` to parse subcommands from `event.get_message_str()` so custom `cmdhead` can also be supported by a catch-all handler if needed.

- [ ] **Step 3: Add image file result for `/phi ill`**

Use `event.image_result(str(path))` when local illustration exists.

- [ ] **Step 4: Verify import/compile**

Run: `python -m compileall main.py phi_core`
Expected: success.

- [ ] **Step 5: Commit offline commands**

```bash
git add main.py phi_core README.md
git commit -m "feat: implement offline phi queries"
```

## Task 4: Binding And Save Cache

**Files:**
- Create: `phi_core/save/__init__.py`
- Create: `phi_core/save/store.py`
- Create: `phi_core/save/codec.py`
- Create: `phi_core/save/client.py`
- Modify: `main.py`
- Modify: `phi_core/render/text.py`

- [ ] **Step 1: Implement `SaveStore`**

Store user bindings in `bindings.json` and normalized saves in `saves/<safe_user_id>.json` under the AstrBot data directory.

- [ ] **Step 2: Implement session token validation**

Require a 25-character alphanumeric token for local token binding.

- [ ] **Step 3: Implement client boundary**

Try Phi Plugin API `/getCloudSaveInfo` and `/getCloudSaves` style endpoints with `httpx`. If response shape is unknown or unavailable, raise `SaveNotAvailable` with a safe message.

- [ ] **Step 4: Implement normalized save parser**

Accept already-normalized save JSON shapes with `saveInfo.summary` and `gameRecord`; reject unsupported encrypted/raw payloads clearly.

- [ ] **Step 5: Wire bind/unbind/clean/update handlers**

`bind` stores token, `unbind` removes binding and save, `clean` aliases full user cleanup, `update` fetches and stores normalized save or explains what failed.

- [ ] **Step 6: Verify compile**

Run: `python -m compileall main.py phi_core`
Expected: success.

- [ ] **Step 7: Commit save boundary**

```bash
git add main.py phi_core README.md
git commit -m "feat: add phi save binding and cache"
```

## Task 5: Query Calculations

**Files:**
- Create: `phi_core/query/__init__.py`
- Create: `phi_core/query/b30.py`
- Create: `phi_core/query/score.py`
- Create: `phi_core/query/user_info.py`
- Modify: `main.py`
- Modify: `phi_core/render/text.py`

- [ ] **Step 1: Implement RKS formula**

If `acc < 70`, rks is `0`; otherwise rks is `((acc - 55) / 45) ** 2 * difficulty`.

- [ ] **Step 2: Implement record extraction**

Read `gameRecord` by song id and difficulty index, attach catalog song/chart metadata, skip LEGACY for B30.

- [ ] **Step 3: Implement B30 result**

Sort records by rks desc, take configured max display, show official `rankingScore` if available and computed average for top 30.

- [ ] **Step 4: Implement score lookup**

Find a song via catalog search, list available records by EZ/HD/IN/AT.

- [ ] **Step 5: Implement user info summary**

Show player id/name, rks, challenge rank, game version, record counts, AP/FC counts when inferable.

- [ ] **Step 6: Wire b30/rks/score/info handlers**

Require cached save and return `/phi update` guidance when missing.

- [ ] **Step 7: Verify compile**

Run: `python -m compileall main.py phi_core`
Expected: success.

- [ ] **Step 8: Commit query core**

```bash
git add main.py phi_core README.md
git commit -m "feat: implement phi query core calculations"
```

## Task 6: Final Verification

**Files:**
- Modify if needed: any files with compile/test issues.

- [ ] **Step 1: Run status check**

Run: `git status --short`
Expected: only intended changes or clean after final commit.

- [ ] **Step 2: Run compile verification**

Run: `python -m compileall .`
Expected: all Python files compile.

- [ ] **Step 3: Run a smoke script for data/search**

Run a short Python import script that loads the catalog and searches for a known song from `info.csv`.

- [ ] **Step 4: Update README if verification changes behavior**

Document known limitation: direct Phigros cloud decoding may need a later pass if API does not return normalized save JSON.

- [ ] **Step 5: Final commit if needed**

```bash
git add .
git commit -m "docs: update phi query core verification notes"
```
