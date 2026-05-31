from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from ..paths import PluginPaths

ILLUSTRATION_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
ONLINE_ILL_BASE = "https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main"
_ONLINE_ILL_PREFIX = f"{ONLINE_ILL_BASE}/"
_ONLINE_ILL_HOST = "raw.githubusercontent.com"
_ONLINE_ILL_PATH_PREFIX = "/Catrong/phi-plugin-ill/"


def find_illustration_file(paths: PluginPaths, song_id: str, *, prefer_low: bool = False) -> Path | None:
    folders = [
        paths.downloaded_original_ill / "illLow",
        paths.downloaded_original_ill / "ill",
        paths.downloaded_original_ill / "SP",
        paths.downloaded_original_ill,
        paths.original_ill / "illLow",
        paths.original_ill / "ill",
        paths.original_ill / "SP",
        paths.original_ill,
    ]
    if not prefer_low:
        folders = [
            paths.downloaded_original_ill / "ill",
            paths.downloaded_original_ill / "SP",
            paths.downloaded_original_ill,
            paths.downloaded_original_ill / "illLow",
            paths.original_ill / "ill",
            paths.original_ill / "SP",
            paths.original_ill,
            paths.original_ill / "illLow",
        ]
    for folder in folders:
        found = _find_named_illustration(folder, song_id)
        if found is not None:
            return found
    return None


def find_background_illustration_file(paths: PluginPaths, song_id: str) -> Path | None:
    folders = [
        paths.downloaded_original_ill / "illBlur",
        paths.original_ill / "illBlur",
        paths.downloaded_original_ill / "illLow",
        paths.original_ill / "illLow",
        paths.downloaded_original_ill / "ill",
        paths.original_ill / "ill",
        paths.downloaded_original_ill / "SP",
        paths.original_ill / "SP",
        paths.downloaded_original_ill,
        paths.original_ill,
    ]
    for folder in folders:
        found = _find_named_illustration(folder, song_id)
        if found is not None:
            return found
    return None


def random_illustration_file(paths: PluginPaths, *, rng: random.Random | None = None) -> Path | None:
    candidates = _available_illustrations(paths)
    if not candidates:
        return None
    return (rng or random.Random()).choice(candidates)


def random_background_source(paths: PluginPaths, *, rng: random.Random | None = None) -> Path | str | None:
    candidates = background_source_candidates(paths, rng=rng, online_limit=1)
    return candidates[0] if candidates else None


def background_source_candidates(
    paths: PluginPaths,
    *,
    rng: random.Random | None = None,
    online_limit: int = 12,
) -> list[Path | str]:
    chooser = rng or random.Random()
    local = _available_background_illustrations(paths)
    chooser.shuffle(local)
    if use_remote_illustrations(paths):
        remote = [background_illustration_url(path.stem) for path in local if path.stem]
        if remote:
            return remote
        ids = _available_online_illustration_ids(paths)
        chooser.shuffle(ids)
        return [
            f"{ONLINE_ILL_BASE}/illBlur/{quote(f'{song_id}.png')}"
            for song_id in ids[:max(0, online_limit)]
        ]
    if local:
        return local

    ids = _available_online_illustration_ids(paths)
    chooser.shuffle(ids)
    online = [
        f"{ONLINE_ILL_BASE}/illBlur/{quote(f'{song_id}.png')}"
        for song_id in ids[:max(0, online_limit)]
    ]

    fallback = _available_other_illustrations(paths)
    chooser.shuffle(fallback)
    return [*online, *fallback]


def use_remote_illustrations(paths: PluginPaths) -> bool:
    source = str(getattr(paths, "illustration_source", "local") or "local").strip().casefold()
    return source in {"remote", "cloud", "online", "github", "url", "urls"}


def is_online_illustration_url(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    path = unquote(parsed.path)
    return (
        text.startswith(_ONLINE_ILL_PREFIX)
        or (host == _ONLINE_ILL_HOST and path.startswith(_ONLINE_ILL_PATH_PREFIX))
    )


def illustration_url(song_id: str, *, prefer_low: bool = False) -> str:
    folder = "illLow" if prefer_low else "ill"
    return _online_url(folder, song_id)


def background_illustration_url(song_id: str) -> str:
    return _online_url("illBlur", song_id)


def online_url_for_local_path(paths: PluginPaths, path: Path) -> str | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    roots = [paths.downloaded_original_ill, paths.original_ill]
    for root in roots:
        try:
            relative = resolved.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        if not relative.parts:
            return None
        return f"{ONLINE_ILL_BASE}/{quote(relative.as_posix())}"
    return None


def _online_url(folder: str, song_id: str) -> str:
    candidates = _candidate_names(song_id)
    name = candidates[0] if candidates else str(song_id).strip()
    return f"{ONLINE_ILL_BASE}/{folder}/{quote(f'{name}.png')}"


def _available_illustrations(paths: PluginPaths) -> list[Path]:
    folders = [
        paths.downloaded_original_ill / "ill",
        paths.downloaded_original_ill / "SP",
        paths.downloaded_original_ill,
        paths.original_ill / "ill",
        paths.original_ill / "SP",
        paths.original_ill,
        paths.other_ill,
        paths.downloaded_original_ill / "illLow",
        paths.original_ill / "illLow",
    ]
    seen: set[Path] = set()
    result: list[Path] = []
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in ILLUSTRATION_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(path)
    return result


def _available_background_illustrations(paths: PluginPaths) -> list[Path]:
    folders = [
        paths.downloaded_original_ill / "illBlur",
        paths.original_ill / "illBlur",
        paths.downloaded_original_ill / "illLow",
        paths.original_ill / "illLow",
        paths.downloaded_original_ill / "ill",
        paths.original_ill / "ill",
        paths.downloaded_original_ill / "SP",
        paths.original_ill / "SP",
        paths.downloaded_original_ill,
        paths.original_ill,
    ]
    result: list[Path] = []
    seen: set[Path] = set()
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in ILLUSTRATION_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(path)
    return result


def _available_other_illustrations(paths: PluginPaths) -> list[Path]:
    if not paths.other_ill.exists() or not paths.other_ill.is_dir():
        return []
    return [
        path
        for path in sorted(paths.other_ill.iterdir())
        if path.is_file() and path.suffix.lower() in ILLUSTRATION_EXTENSIONS
    ]


def _available_online_illustration_ids(paths: PluginPaths) -> list[str]:
    ids: list[str] = []
    info_csv = paths.info / "info.csv"
    if info_csv.exists():
        with info_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = str(row.get("id") or "").strip()
                if raw:
                    ids.append(raw.removesuffix(".0"))
    spinfo = paths.info / "spinfo.json"
    if spinfo.exists():
        try:
            data = json.loads(spinfo.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            for raw in data:
                text = str(raw).strip()
                if text:
                    ids.append(text.removesuffix(".0"))
    return sorted(set(ids))


def _find_named_illustration(folder: Path, song_id: str) -> Path | None:
    if not folder.exists() or not folder.is_dir():
        return None
    for name in _candidate_names(song_id):
        for ext in ILLUSTRATION_EXTENSIONS:
            path = folder / f"{name}{ext}"
            if path.exists() and path.is_file():
                return path
    return None


def _candidate_names(song_id: str) -> tuple[str, ...]:
    raw = str(song_id).strip()
    base = raw.removesuffix(".0")
    with_suffix = raw if raw.endswith(".0") else f"{raw}.0"
    result: list[str] = []
    for item in (raw, base, with_suffix):
        if item and item not in result:
            result.append(item)
    return tuple(result)
