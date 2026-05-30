from __future__ import annotations

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
