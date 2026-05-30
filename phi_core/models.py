from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEVELS: tuple[str, ...] = ("EZ", "HD", "IN", "AT")
ALL_LEVELS: tuple[str, ...] = ("EZ", "HD", "IN", "AT", "LEGACY")
LEVEL_INDEX: dict[str, int] = {name: index for index, name in enumerate(ALL_LEVELS)}


@dataclass(slots=True)
class SongChart:
    rank: str
    difficulty: float | None = None
    difficulty_text: str = ""
    level: str = ""
    combo: int | None = None
    charter: str = ""
    rgba: str = ""


@dataclass(slots=True)
class Song:
    id: str
    title: str
    composer: str = ""
    illustrator: str = ""
    bpm: str = ""
    length: str = ""
    chapter: str = ""
    illustration: str = ""
    illustration_big: str = ""
    sp_info: str = ""
    is_original: bool | None = None
    aliases: list[str] = field(default_factory=list)
    charts: dict[str, SongChart] = field(default_factory=dict)

    @property
    def id_with_suffix(self) -> str:
        return self.id if self.id.endswith(".0") else f"{self.id}.0"

    def display_charts(self) -> list[SongChart]:
        order = {name: index for index, name in enumerate(ALL_LEVELS)}
        return sorted(self.charts.values(), key=lambda c: order.get(c.rank, 99))


@dataclass(slots=True)
class SearchHit:
    song: Song
    score: float
    matched: str


@dataclass(slots=True)
class ChartEntry:
    song_id: str
    song_title: str
    rank: str
    difficulty: float
    difficulty_text: str = ""
    combo: int | None = None


@dataclass(slots=True)
class ScoreRecord:
    song_id: str
    song_title: str
    rank: str
    score: int
    acc: float
    fc: bool
    rating: str
    difficulty: float
    rks: float


@dataclass(slots=True)
class ScoreListEntry:
    chart: ChartEntry
    record: ScoreRecord | None = None
    suggest_acc: float | None = None


@dataclass(slots=True)
class LevelScoreSummary:
    range_text: str
    levels: list[str]
    total_charts: int
    played_charts: int
    phi_count: int
    fc_count: int
    avg_acc: float
    avg_score: float
    highest_difficulty: float
    lowest_difficulty: float
    rank_counts: dict[str, int]
    rating_counts: dict[str, int]


@dataclass(slots=True)
class SuggestEntry:
    chart: ChartEntry
    current: ScoreRecord | None
    target_acc: float
    target_rks: float


@dataclass(slots=True)
class SaveSnapshot:
    user_id: str
    session_token: str = ""
    player_id: str = ""
    player_name: str = ""
    ranking_score: float = 0.0
    challenge_mode_rank: int | str | None = None
    game_version: int | str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Best30Result:
    official_rks: float
    computed_rks: float
    records: list[ScoreRecord]
    total_records: int
    phi_records: list[ScoreRecord] = field(default_factory=list)


@dataclass(slots=True)
class UserSummary:
    player_id: str
    player_name: str
    ranking_score: float
    challenge_mode_rank: int | str | None
    game_version: int | str | None
    total_records: int
    phi_count: int
    fc_count: int


@dataclass(slots=True)
class ProgressScoreChange:
    song_id: str
    song_title: str
    rank: str
    date: str
    score_new: int
    acc_new: float
    fc_new: bool
    rating_new: str
    rks_new: float
    score_old: int | None = None
    acc_old: float | None = None
    fc_old: bool | None = None
    rks_old: float | None = None


@dataclass(slots=True)
class ProgressDay:
    date: str
    update_count: int
    changes: list[ProgressScoreChange] = field(default_factory=list)


@dataclass(slots=True)
class UpdateProgressSummary:
    player_id: str
    player_name: str
    ranking_score: float
    challenge_mode_rank: int | str | None
    modified_at: str
    total_records: int
    current_update_count: int
    shown_changes: int
    recent_days: list[ProgressDay] = field(default_factory=list)
    rks_delta: float | None = None
    challenge_delta: int | float | None = None
    data_money: list[int] | None = None
    data_delta: int | None = None
    is_first_record: bool = False
