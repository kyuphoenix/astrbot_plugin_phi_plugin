from __future__ import annotations

from typing import Any, Iterable

from ..data.loader import SongCatalog, normalize_song_id
from ..models import ALL_LEVELS, LEVELS, Best30Result, SaveSnapshot, ScoreRecord


def rks_from_acc(acc: float, difficulty: float) -> float:
    if acc >= 100:
        return float(difficulty)
    if acc < 70:
        return 0.0
    return float(difficulty) * (((acc - 55.0) / 45.0) ** 2)


def rating_from_score(score: int, fc: bool) -> str:
    if score >= 1_000_000:
        return "phi"
    if fc:
        return "FC"
    if score <= 0:
        return "NEW"
    if score < 700_000:
        return "F"
    if score < 820_000:
        return "C"
    if score < 880_000:
        return "B"
    if score < 920_000:
        return "A"
    if score < 960_000:
        return "S"
    return "V"


def iter_score_records(snapshot: SaveSnapshot, catalog: SongCatalog) -> list[ScoreRecord]:
    raw_records = snapshot.raw.get("gameRecord")
    if not isinstance(raw_records, dict):
        return []

    records: list[ScoreRecord] = []
    for raw_song_id, level_records in raw_records.items():
        song_id = normalize_song_id(str(raw_song_id))
        song = catalog.get(song_id)
        if not song:
            continue
        for index, record_data in _iter_level_records(level_records):
            if index >= len(ALL_LEVELS):
                continue
            rank = ALL_LEVELS[index]
            if rank == "LEGACY":
                continue
            if not isinstance(record_data, dict):
                continue
            score = _as_int(record_data.get("score"))
            acc = _as_float(record_data.get("acc"))
            if score <= 0 and acc <= 0:
                continue
            chart = song.charts.get(rank)
            difficulty = float(chart.difficulty) if chart and chart.difficulty is not None else 0.0
            fc = bool(record_data.get("fc"))
            records.append(ScoreRecord(
                song_id=song.id,
                song_title=song.title,
                rank=rank,
                score=score,
                acc=acc,
                fc=fc,
                rating=rating_from_score(score, fc),
                difficulty=difficulty,
                rks=rks_from_acc(acc, difficulty),
            ))
    return records


def compute_b30(snapshot: SaveSnapshot, catalog: SongCatalog, limit: int = 30) -> Best30Result:
    all_records = iter_score_records(snapshot, catalog)
    sorted_records = sorted(all_records, key=lambda item: item.rks, reverse=True)
    top30 = sorted_records[:30]
    computed = sum(record.rks for record in top30) / 30 if top30 else 0.0
    return Best30Result(
        official_rks=snapshot.ranking_score,
        computed_rks=computed,
        records=sorted_records[:limit],
        total_records=len(all_records),
    )


def _iter_level_records(value: Any) -> Iterable[tuple[int, Any]]:
    if isinstance(value, list):
        yield from enumerate(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            try:
                yield int(key), item
            except (TypeError, ValueError):
                if str(key).upper() in LEVELS:
                    yield LEVELS.index(str(key).upper()), item


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
