from __future__ import annotations

from ..data.loader import SongCatalog
from ..models import SaveSnapshot, ScoreRecord, Song
from .b30 import iter_score_records


def find_song_scores(snapshot: SaveSnapshot, catalog: SongCatalog, song: Song) -> list[ScoreRecord]:
    return [record for record in iter_score_records(snapshot, catalog) if record.song_id == song.id]
