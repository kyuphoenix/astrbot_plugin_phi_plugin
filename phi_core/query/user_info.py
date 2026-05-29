from __future__ import annotations

from ..data.loader import SongCatalog
from ..models import SaveSnapshot, UserSummary
from .b30 import iter_score_records


def summarize_user(snapshot: SaveSnapshot, catalog: SongCatalog) -> UserSummary:
    records = iter_score_records(snapshot, catalog)
    return UserSummary(
        player_id=snapshot.player_id,
        player_name=snapshot.player_name,
        ranking_score=snapshot.ranking_score,
        challenge_mode_rank=snapshot.challenge_mode_rank,
        game_version=snapshot.game_version,
        total_records=len(records),
        phi_count=sum(1 for record in records if record.rating == "phi"),
        fc_count=sum(1 for record in records if record.fc or record.rating == "phi"),
    )
