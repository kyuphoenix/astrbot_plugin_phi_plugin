from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PluginPaths:
    root: Path
    resources: Path
    info: Path
    other_ill: Path
    original_ill: Path
    data_dir: Path
    downloads: Path
    cache: Path
    downloaded_original_ill: Path

    @classmethod
    def from_root(cls, root: Path, data_dir: Path | None = None) -> "PluginPaths":
        root = root.resolve()
        resources = root / "resources"
        data_root = (data_dir or (root / "data")).resolve()
        return cls(
            root=root,
            resources=resources,
            info=resources / "info",
            other_ill=resources / "otherill",
            original_ill=resources / "original_ill",
            data_dir=data_root,
            downloads=data_root / "downloads",
            cache=data_root / "cache",
            downloaded_original_ill=data_root / "downloads" / "original_ill",
        )

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.downloaded_original_ill.mkdir(parents=True, exist_ok=True)
