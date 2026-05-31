from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..data.loader import SongCatalog, normalize_song_id
from ..models import ChartEntry, LEVELS, ScoreRecord
from .b30 import rating_from_score, rks_from_acc
from .progress import _open_score_item, _parse_datetime, format_datetime, money_to_kib, normalize_history


@dataclass(slots=True)
class ChapterRankSummary:
    total: int = 0
    played: int = 0
    acc_sum: float = 0.0

    @property
    def average_acc(self) -> float:
        return self.acc_sum / self.total if self.total else 0.0


@dataclass(slots=True)
class ChapterSummary:
    name: str
    total_charts: int
    played_charts: int
    rating_counts: dict[str, int]
    rank_counts: dict[str, ChapterRankSummary]
    top_records: list[ScoreRecord] = field(default_factory=list)


@dataclass(slots=True)
class AchievementRow:
    difficulty: float
    total: int
    played: int
    min_rating: str
    min_score: int
    avg_acc: float
    phi_count: int
    fc_count: int


@dataclass(slots=True)
class HistoryScoreEvent:
    date: datetime
    record: ScoreRecord


@dataclass(slots=True)
class HistoryB30Change:
    date: str
    new_phi: list[tuple[int, ScoreRecord]] = field(default_factory=list)
    new_b27: list[tuple[int, ScoreRecord]] = field(default_factory=list)
    exit_phi: list[ScoreRecord] = field(default_factory=list)
    exit_b27: list[ScoreRecord] = field(default_factory=list)


@dataclass(slots=True)
class HistorySummary:
    total_days: int
    total_updates: int
    most_played: list[tuple[str, int]]
    rks_max_up: tuple[str, float] | None
    rks_max_down: tuple[str, float] | None
    most_new_records: list[tuple[str, int]]
    data_max_up: tuple[str, int] | None
    data_max_down: tuple[str, int] | None
    latest_push_times: list[tuple[str, str]]
    most_ap_days: list[tuple[str, int]]
    total_score_records: int


def compute_chapter_summary(snapshot_records: list[ScoreRecord], catalog: SongCatalog, chapter_query: str) -> ChapterSummary | None:
    chapter = resolve_chapter_name(catalog, chapter_query)
    if chapter is None:
        return None

    record_map = {(record.song_id, record.rank): record for record in snapshot_records}
    rank_counts = {rank: ChapterRankSummary() for rank in LEVELS}
    rating_counts = {name: 0 for name in ("phi", "FC", "V", "S", "A", "B", "C", "F", "NEW")}
    top_records: list[ScoreRecord] = []
    total = 0
    played = 0

    for song in catalog.all_songs():
        if chapter != "ALL" and song.chapter != chapter:
            continue
        for chart in song.display_charts():
            if chart.rank not in LEVELS or chart.difficulty is None:
                continue
            total += 1
            rank_summary = rank_counts[chart.rank]
            rank_summary.total += 1
            record = record_map.get((song.id, chart.rank))
            if record is None:
                rating_counts["NEW"] += 1
                continue
            played += 1
            rank_summary.played += 1
            rank_summary.acc_sum += record.acc
            rating_counts[record.rating] = rating_counts.get(record.rating, 0) + 1
            top_records.append(record)

    top_records.sort(key=lambda item: item.rks, reverse=True)
    return ChapterSummary(
        name="AllSong" if chapter == "ALL" else chapter,
        total_charts=total,
        played_charts=played,
        rating_counts=rating_counts,
        rank_counts=rank_counts,
        top_records=top_records[:12],
    )


def resolve_chapter_name(catalog: SongCatalog, query: str) -> str | None:
    text = (query or "").strip()
    if not text or text.casefold() in {"all", "allsong", "全部"}:
        return "ALL"
    key = _normalize(text)
    chapters = {song.chapter for song in catalog.all_songs() if song.chapter}
    for chapter in chapters:
        if _normalize(chapter) == key or key in _normalize(chapter):
            return chapter
    return None


def compute_achievement_rows(snapshot_records: list[ScoreRecord], catalog: SongCatalog, difficulty_floor: int) -> list[AchievementRow]:
    charts: list[ChartEntry] = []
    for song in catalog.all_songs():
        for chart in song.display_charts():
            if chart.rank in LEVELS and chart.difficulty is not None:
                charts.append(ChartEntry(
                    song_id=song.id,
                    song_title=song.title,
                    rank=chart.rank,
                    difficulty=float(chart.difficulty),
                    difficulty_text=chart.difficulty_text or f"{chart.difficulty:.1f}",
                    combo=chart.combo,
                ))
    return compute_achievement_rows_for_charts(snapshot_records, charts, difficulty_floor)


def compute_achievement_rows_for_charts(
    snapshot_records: list[ScoreRecord],
    charts: list[ChartEntry],
    difficulty_floor: int,
) -> list[AchievementRow]:
    record_map = {(record.song_id, record.rank): record for record in snapshot_records}
    rows: list[AchievementRow] = []
    for offset in range(10):
        difficulty = round(difficulty_floor + offset / 10, 1)
        matched_charts = [
            (chart.song_id, chart.rank)
            for chart in charts
            if chart.rank in LEVELS and round(chart.difficulty, 1) == difficulty
        ]
        if not matched_charts:
            continue
        records = [record_map.get(key) for key in matched_charts]
        played_records = [record for record in records if record is not None]
        min_score = min((record.score if record else 0) for record in records)
        all_fc = all(bool(record and record.fc) for record in records)
        rows.append(AchievementRow(
            difficulty=difficulty,
            total=len(matched_charts),
            played=len(played_records),
            min_rating=rating_from_score(min_score, all_fc),
            min_score=min_score,
            avg_acc=sum(record.acc for record in played_records) / len(matched_charts),
            phi_count=sum(1 for record in played_records if record.rating == "phi"),
            fc_count=sum(1 for record in played_records if record.fc),
        ))
    return rows


def iter_history_score_events(history: dict[str, Any], catalog: SongCatalog) -> list[HistoryScoreEvent]:
    normalized = normalize_history(history)
    events: list[HistoryScoreEvent] = []
    score_history = normalized.get("scoreHistory") if isinstance(normalized.get("scoreHistory"), dict) else {}
    for raw_song_id, level_map in score_history.items():
        song_id = normalize_song_id(str(raw_song_id))
        song = catalog.get(song_id)
        if not song or not isinstance(level_map, dict):
            continue
        for rank, items in level_map.items():
            rank = str(rank).upper()
            if rank not in LEVELS or not isinstance(items, list):
                continue
            chart = song.charts.get(rank)
            difficulty = float(chart.difficulty) if chart and chart.difficulty is not None else 0.0
            for raw_item in items:
                opened = _open_score_item(raw_item)
                if opened is None:
                    continue
                score = int(opened["score"])
                acc = float(opened["acc"])
                fc = bool(opened["fc"])
                events.append(HistoryScoreEvent(
                    date=opened["date"],
                    record=ScoreRecord(
                        song_id=song.id,
                        song_title=song.title,
                        rank=rank,
                        score=score,
                        acc=acc,
                        fc=fc,
                        rating=rating_from_score(score, fc),
                        difficulty=difficulty,
                        rks=rks_from_acc(acc, difficulty),
                    ),
                ))
    events.sort(key=lambda item: item.date)
    return events


def compute_history_b30_changes(history: dict[str, Any], catalog: SongCatalog, *, limit: int = 12) -> list[HistoryB30Change]:
    grouped: dict[datetime, list[ScoreRecord]] = defaultdict(list)
    for event in iter_history_score_events(history, catalog):
        grouped[event.date].append(event.record)

    phi: list[ScoreRecord] = []
    b27: list[ScoreRecord] = []
    changes: list[HistoryB30Change] = []

    for date in sorted(grouped):
        records = sorted(grouped[date], key=lambda item: item.rks, reverse=True)
        old_phi = list(phi)
        old_b27 = list(b27)
        old_phi_keys = [_record_key(item) for item in old_phi]
        old_b27_keys = [_record_key(item) for item in old_b27]

        ap_records = [record for record in records if record.acc >= 100]
        ap_keys = {_record_key(item) for item in ap_records}
        record_keys = {_record_key(item) for item in records}
        phi = [item for item in phi if _record_key(item) not in ap_keys]
        b27 = [item for item in b27 if _record_key(item) not in record_keys]
        phi = sorted([*phi, *ap_records], key=lambda item: item.rks, reverse=True)[:3]
        b27 = sorted([*b27, *records], key=lambda item: item.rks, reverse=True)[:27]

        new_phi_keys = [_record_key(item) for item in phi]
        new_b27_keys = [_record_key(item) for item in b27]
        change = HistoryB30Change(date=format_datetime(date))
        for index, record in enumerate(phi, 1):
            if _record_key(record) not in old_phi_keys:
                change.new_phi.append((index, record))
        for index, record in enumerate(b27, 1):
            if _record_key(record) not in old_b27_keys:
                change.new_b27.append((index, record))
        for record in old_phi:
            if _record_key(record) not in new_phi_keys:
                change.exit_phi.append(record)
        for record in old_b27:
            if _record_key(record) not in new_b27_keys:
                change.exit_b27.append(record)
        if change.new_phi or change.new_b27 or change.exit_phi or change.exit_b27:
            changes.append(change)

    return list(reversed(changes))[:limit]


def analyze_history(history: dict[str, Any], catalog: SongCatalog) -> HistorySummary:
    normalized = normalize_history(history)
    score_events = iter_history_score_events(normalized, catalog)
    rks_events = _series_events(normalized.get("rks"))
    data_events = _series_events(normalized.get("data"))
    challenge_events = _series_events(normalized.get("challengeModeRank"))

    day_set = {event.date.strftime("%Y-%m-%d") for event in score_events}
    day_set.update(date.strftime("%Y-%m-%d") for date, _ in rks_events)
    day_set.update(date.strftime("%Y-%m-%d") for date, _ in data_events)
    day_set.update(date.strftime("%Y-%m-%d") for date, _ in challenge_events)

    update_set = {event.date.timestamp() for event in score_events}
    update_set.update(date.timestamp() for date, _ in rks_events)
    update_set.update(date.timestamp() for date, _ in data_events)
    update_set.update(date.timestamp() for date, _ in challenge_events)

    most_played_counter = Counter(event.record.song_title for event in score_events)
    most_new_records = _new_record_days(score_events)
    most_ap_days = Counter(event.date.strftime("%Y-%m-%d") for event in score_events if event.record.acc >= 100)
    latest_push = _latest_push_times(score_events)

    return HistorySummary(
        total_days=len(day_set),
        total_updates=len(update_set),
        most_played=most_played_counter.most_common(3),
        rks_max_up=_best_delta_day(rks_events, want_up=True),
        rks_max_down=_best_delta_day(rks_events, want_up=False),
        most_new_records=most_new_records.most_common(3),
        data_max_up=_best_data_delta_day(data_events, want_up=True),
        data_max_down=_best_data_delta_day(data_events, want_up=False),
        latest_push_times=latest_push[:3],
        most_ap_days=most_ap_days.most_common(3),
        total_score_records=len(score_events),
    )


def _series_events(series: Any) -> list[tuple[datetime, Any]]:
    events: list[tuple[datetime, Any]] = []
    if not isinstance(series, list):
        return events
    for item in series:
        if not isinstance(item, dict):
            continue
        date = _parse_datetime(item.get("date"))
        if date is not None:
            events.append((date, item.get("value")))
    return sorted(events, key=lambda item: item[0])


def _new_record_days(events: list[HistoryScoreEvent]) -> Counter[str]:
    best_by_chart: dict[tuple[str, str], tuple[int, float]] = {}
    counter: Counter[str] = Counter()
    for event in events:
        key = (event.record.song_id, event.record.rank)
        best = best_by_chart.get(key)
        current = (event.record.score, event.record.acc)
        if best is None or current[0] > best[0] or (current[0] == best[0] and current[1] > best[1]):
            counter[event.date.strftime("%Y-%m-%d")] += 1
            best_by_chart[key] = current
    return counter


def _latest_push_times(events: list[HistoryScoreEvent]) -> list[tuple[str, str]]:
    latest: dict[str, datetime] = {}
    for event in events:
        day = event.date.strftime("%Y-%m-%d")
        if day not in latest or event.date > latest[day]:
            latest[day] = event.date
    return sorted(
        ((day, value.strftime("%H:%M:%S")) for day, value in latest.items()),
        key=lambda item: item[1],
        reverse=True,
    )


def _best_delta_day(events: list[tuple[datetime, Any]], *, want_up: bool) -> tuple[str, float] | None:
    deltas: dict[str, float] = defaultdict(float)
    previous: float | None = None
    for date, value in events:
        try:
            current = float(value)
        except (TypeError, ValueError):
            continue
        if previous is not None:
            delta = current - previous
            if delta:
                deltas[date.strftime("%Y-%m-%d")] += delta
        previous = current
    if not deltas:
        return None
    picked = max(deltas.items(), key=lambda item: item[1]) if want_up else min(deltas.items(), key=lambda item: item[1])
    if want_up and picked[1] <= 0:
        return None
    if not want_up and picked[1] >= 0:
        return None
    return picked


def _best_data_delta_day(events: list[tuple[datetime, Any]], *, want_up: bool) -> tuple[str, int] | None:
    converted = [(date, money_to_kib(value)) for date, value in events]
    deltas: dict[str, int] = defaultdict(int)
    previous: int | None = None
    for date, value in converted:
        if value is None:
            continue
        if previous is not None:
            delta = value - previous
            if delta:
                deltas[date.strftime("%Y-%m-%d")] += delta
        previous = value
    if not deltas:
        return None
    picked = max(deltas.items(), key=lambda item: item[1]) if want_up else min(deltas.items(), key=lambda item: item[1])
    if want_up and picked[1] <= 0:
        return None
    if not want_up and picked[1] >= 0:
        return None
    return picked


def _record_key(record: ScoreRecord) -> tuple[str, str]:
    return (record.song_id, record.rank)


def _normalize(value: str) -> str:
    return "".join(str(value).casefold().split())
