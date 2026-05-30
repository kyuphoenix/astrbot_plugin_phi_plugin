from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import PluginConfig
from ..data.illustrations import find_illustration_file
from ..data import SongCatalog, SongSearcher
from ..models import SaveSnapshot, Song
from ..paths import PluginPaths
from ..save import PhiApiClient, SaveNotAvailable, SaveStore, TapTapQrLogin, normalize_save

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
    taptap: TapTapQrLogin | None = None
    html_render: Callable[[str, dict, bool, dict | None], Awaitable[str | bytes]] | None = None
    sender: Callable[[CommandResult], Awaitable[None]] | None = None
    is_admin: bool = False
    session_id: str = ""

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
        original = find_illustration_file(self.paths, song.id)
        if original is not None:
            candidates.append(original)
        if song.illustration:
            candidates.append(self.paths.other_ill / song.illustration)
        if song.illustration_big:
            candidates.append(self.paths.other_ill / song.illustration_big)
        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return None
