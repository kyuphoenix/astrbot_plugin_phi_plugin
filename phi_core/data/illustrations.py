from __future__ import annotations

import random
from pathlib import Path

from ..paths import PluginPaths

ILLUSTRATION_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


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
