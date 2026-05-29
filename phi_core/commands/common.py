from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import PluginConfig
from ..data import SongCatalog, SongSearcher
from ..models import SaveSnapshot, Song
from ..paths import PluginPaths
from ..save import PhiApiClient, SaveNotAvailable, SaveStore, normalize_save

ResultKind = Literal["text", "image"]


@dataclass(slots=True)
class CommandResult:
    kind: ResultKind
    value: str

    @classmethod
    def text(cls, value: str) -> "CommandResult":
        return cls(kind="text", value=value)

    @classmethod
    def image(cls, value: str | Path) -> "CommandResult":
        return cls(kind="image", value=str(value))


@dataclass(slots=True)
class CommandContext:
    config: PluginConfig
    paths: PluginPaths
    catalog: SongCatalog
    searcher: SongSearcher
    store: SaveStore
    client: PhiApiClient

    def load_snapshot(self, user_id: str) -> SaveSnapshot | None:
        raw = self.store.load_snapshot(user_id)
        if not raw:
            return None
        token = self.store.get_token(user_id) or str(raw.get("session") or "")
        try:
            return normalize_save(user_id, token, raw)
        except SaveNotAvailable:
            return None

    def find_illustration(self, song: Song) -> Path | None:
        candidates: list[Path] = []
        base_id = song.id.removesuffix(".0")
        for folder in [
            self.paths.downloaded_original_ill,
            self.paths.downloaded_original_ill / "ill",
            self.paths.downloaded_original_ill / "SP",
            self.paths.original_ill,
            self.paths.original_ill / "ill",
            self.paths.original_ill / "SP",
        ]:
            candidates.append(folder / f"{base_id}.png")
        if song.illustration:
            candidates.append(self.paths.other_ill / song.illustration)
        if song.illustration_big:
            candidates.append(self.paths.other_ill / song.illustration_big)
        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return None
