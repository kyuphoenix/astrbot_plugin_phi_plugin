from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from urllib.parse import quote

from ..paths import PluginPaths

ILLUSTRATION_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
ONLINE_ILL_BASE = "https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main"


def find_illustration_file(paths: PluginPaths, song_id: str, *, prefer_low: bool = False) -> Path | None:
    base_id = str(song_id).removesuffix(".0")
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
        for ext in ILLUSTRATION_EXTENSIONS:
            path = folder / f"{base_id}{ext}"
            if path.exists() and path.is_file():
                return path
    return None


def random_illustration_file(paths: PluginPaths, *, rng: random.Random | None = None) -> Path | None:
    candidates = _available_illustrations(paths)
    if not candidates:
        return None
    return (rng or random.Random()).choice(candidates)


def random_background_source(paths: PluginPaths, *, rng: random.Random | None = None) -> Path | str | None:
    local = _available_background_illustrations(paths)
    chooser = rng or random.Random()
    if local:
        return chooser.choice(local)
    ids = _available_online_illustration_ids(paths)
    if ids:
        filename = quote(f"{chooser.choice(ids)}.png")
        return f"{ONLINE_ILL_BASE}/illBlur/{filename}"
    fallback = _available_other_illustrations(paths)
    if fallback:
        return chooser.choice(fallback)
    return None


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
