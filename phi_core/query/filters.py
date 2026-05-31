from __future__ import annotations

from dataclasses import dataclass
import math
import random
import re
from typing import Iterable

from ..data.loader import SongCatalog, normalize_song_id
from ..models import ChartEntry, LEVELS, LevelScoreSummary, SaveSnapshot, ScoreListEntry, ScoreRecord, SuggestEntry
from .b30 import iter_score_records, rks_from_acc

RATING_ORDER = ("NEW", "F", "C", "B", "A", "S", "V", "FC", "PHI")
_LEVEL_RE = re.compile(r"\b(EZ|HD|IN|AT)\b", re.IGNORECASE)
_RATING_RE = re.compile(r"\b(NEW|F|C|B|A|S|V|FC|PHI|AP)\b", re.IGNORECASE)
_RANGE_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)(?:\s*(?:-|~|～|至|到)\s*(\d+(?:\.\d+)?))?([+-])?")


@dataclass(slots=True)
class RangeFilter:
    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def label(self) -> str:
        if self.low == self.high:
            return _fmt_number(self.low)
        return f"{_fmt_number(self.low)}-{_fmt_number(self.high)}"


@dataclass(slots=True)
class ScoreFilter:
    difficulty: RangeFilter
    acc: RangeFilter
    levels: set[str]
    ratings: set[str]

    def request_lines(self) -> list[str]:
        return [
            f"定数 {self.difficulty.label()}",
            f"ACC {self.acc.label()}",
            "难度 " + "/".join(level for level in LEVELS if level in self.levels),
            "评级 " + "/".join(rating for rating in RATING_ORDER if rating in self.ratings),
        ]

    def original_request_lines(self) -> list[str]:
        return [
            f"定数 {self.difficulty.label()}",
            f"ACC {self.acc.label()}",
        ]


def all_chart_entries(catalog: SongCatalog) -> list[ChartEntry]:
    entries: list[ChartEntry] = []
    for song in catalog.all_songs():
        for chart in song.display_charts():
            if chart.difficulty is None:
                continue
            entries.append(
                ChartEntry(
                    song_id=song.id,
                    song_title=song.title,
                    rank=chart.rank,
                    difficulty=float(chart.difficulty),
                    difficulty_text=chart.difficulty_text or f"{chart.difficulty:.1f}",
                    combo=chart.combo,
                )
            )
    return entries


def records_by_chart(snapshot: SaveSnapshot, catalog: SongCatalog) -> dict[tuple[str, str], ScoreRecord]:
    return {(record.song_id, record.rank): record for record in iter_score_records(snapshot, catalog)}


def parse_levels(text: str) -> set[str]:
    levels = {match.group(1).upper() for match in _LEVEL_RE.finditer(text)}
    return levels or set(LEVELS)


def parse_ratings(text: str) -> set[str]:
    ratings = {("PHI" if match.group(1).upper() == "AP" else match.group(1).upper()) for match in _RATING_RE.finditer(text)}
    return ratings or set(RATING_ORDER)


def parse_range(
    text: str,
    *,
    default: tuple[float, float],
    max_value: float,
    int_bucket: bool = False,
) -> RangeFilter:
    match = _RANGE_RE.search(text)
    if not match:
        return RangeFilter(default[0], default[1])

    start = float(match.group(1))
    end_text = match.group(2)
    suffix = match.group(3)
    if end_text is not None:
        end = float(end_text)
        if int_bucket and end.is_integer() and ".0" not in end_text:
            end += 0.9
    elif suffix == "+":
        end = max_value
    elif suffix == "-":
        end = default[0]
    elif int_bucket and start.is_integer() and ".0" not in match.group(1):
        end = start + 0.9
    else:
        end = start

    low, high = sorted((start, end))
    low = max(default[0], low)
    high = min(max_value, high)
    return RangeFilter(low, high)


def parse_score_filter(args: str, *, max_difficulty: float | None = None) -> ScoreFilter:
    max_diff = max_difficulty or 18.0
    text = args.upper()
    acc_match = re.search(r"-ACC\s*\d+(?:\.\d+)?(?:\s*(?:-|~|～|至|到)\s*\d+(?:\.\d+)?|\s*[+-])?", text)
    acc_text = acc_match.group(0).replace("-ACC", "", 1) if acc_match else ""
    if acc_match:
        text = text.replace(acc_match.group(0), " ")
    dif_match = re.search(r"(?:-DIF\s*)?\d+(?:\.\d+)?(?:\s*(?:-|~|～|至|到)\s*\d+(?:\.\d+)?|\s*[+-])?", text)
    dif_text = dif_match.group(0).replace("-DIF", "", 1) if dif_match else ""

    return ScoreFilter(
        difficulty=parse_range(dif_text, default=(0.0, max_diff), max_value=max_diff, int_bucket=True),
        acc=parse_range(acc_text, default=(0.0, 100.0), max_value=100.0),
        levels=parse_levels(args),
        ratings=parse_ratings(args),
    )


def filter_score_entries(snapshot: SaveSnapshot, catalog: SongCatalog, score_filter: ScoreFilter) -> list[ScoreListEntry]:
    record_map = records_by_chart(snapshot, catalog)
    entries: list[ScoreListEntry] = []
    for chart in all_chart_entries(catalog):
        if chart.rank not in score_filter.levels:
            continue
        if not score_filter.difficulty.contains(chart.difficulty):
            continue
        record = record_map.get((chart.song_id, chart.rank))
        rating = "NEW" if record is None else ("PHI" if record.rating == "phi" else record.rating.upper())
        if rating not in score_filter.ratings:
            continue
        if record is not None and not score_filter.acc.contains(record.acc):
            continue
        if record is None and score_filter.acc.low > 0:
            continue
        entries.append(ScoreListEntry(chart=chart, record=record))
    return sorted(entries, key=lambda item: (-item.chart.difficulty, item.chart.song_title, item.chart.rank))


def summarize_level_scores(snapshot: SaveSnapshot, catalog: SongCatalog, score_filter: ScoreFilter) -> LevelScoreSummary:
    entries = filter_score_entries(snapshot, catalog, score_filter)
    played = [entry for entry in entries if entry.record is not None]
    scores = [entry.record.score for entry in played if entry.record]
    accs = [entry.record.acc for entry in played if entry.record]
    difficulties = [entry.chart.difficulty for entry in entries]
    rating_counts = {rating: 0 for rating in RATING_ORDER}
    rank_counts = {level: 0 for level in LEVELS}
    for entry in entries:
        rank_counts[entry.chart.rank] = rank_counts.get(entry.chart.rank, 0) + 1
        rating = "NEW" if entry.record is None else ("PHI" if entry.record.rating == "phi" else entry.record.rating.upper())
        rating_counts[rating] = rating_counts.get(rating, 0) + 1

    return LevelScoreSummary(
        range_text=score_filter.difficulty.label(),
        levels=[level for level in LEVELS if level in score_filter.levels],
        total_charts=len(entries),
        played_charts=len(played),
        phi_count=rating_counts.get("PHI", 0),
        fc_count=sum(1 for entry in played if entry.record and (entry.record.fc or entry.record.rating == "phi")),
        avg_acc=sum(accs) / len(accs) if accs else 0.0,
        avg_score=sum(scores) / len(scores) if scores else 0.0,
        highest_difficulty=max(difficulties) if difficulties else 0.0,
        lowest_difficulty=min(difficulties) if difficulties else 0.0,
        rank_counts=rank_counts,
        rating_counts=rating_counts,
    )


def top_records(snapshot: SaveSnapshot, catalog: SongCatalog, *, limit: int, mode: str = "best", min_acc: float | None = None) -> list[ScoreRecord]:
    records = iter_score_records(snapshot, catalog)
    if min_acc is not None:
        records = [record for record in records if record.acc >= min_acc]
    if mode == "p":
        records = [record for record in records if record.acc >= 100]
    elif mode == "fc":
        records = [record for record in records if record.fc and record.score < 1_000_000]
    elif mode == "x":
        chart_map = {(entry.song_id, entry.rank): entry for entry in all_chart_entries(catalog)}
        records = [record for record in records if _is_one_good_like(record, chart_map.get((record.song_id, record.rank)))]
    return sorted(records, key=lambda item: item.rks, reverse=True)[:limit]


def compute_average_rks(records: Iterable[ScoreRecord], denominator: int = 30) -> float:
    selected = list(records)[:denominator]
    return sum(record.rks for record in selected) / denominator if selected else 0.0


def target_acc_for_rks(target_rks: float, difficulty: float) -> float | None:
    if difficulty <= 0:
        return None
    answer = 45.0 * math.sqrt(max(target_rks, 0.0) / difficulty) + 55.0
    if answer >= 100:
        return None
    return answer


def suggest_entries(
    snapshot: SaveSnapshot,
    catalog: SongCatalog,
    *,
    score_filter: ScoreFilter | None = None,
    avg_lookup: dict[tuple[str, str], float] | None = None,
    per_group_limit: int = 3,
) -> list[SuggestEntry]:
    records = iter_score_records(snapshot, catalog)
    sorted_records = sorted(records, key=lambda item: item.rks, reverse=True)
    floor_rks = sorted_records[26].rks if len(sorted_records) > 26 else 0.0
    min_up = _min_up_rks(snapshot.ranking_score) * 30
    phi_floor = max((record.rks for record in sorted_records if record.acc >= 100), default=None)
    record_map = {(record.song_id, record.rank): record for record in records}
    avg_lookup = avg_lookup or {}
    eligible_song_ids = _record_song_ids(snapshot)
    suggestions: dict[int, list[SuggestEntry]] = {index: [] for index in range(6)}
    for chart in all_chart_entries(catalog):
        if eligible_song_ids and chart.song_id not in eligible_song_ids:
            continue
        if score_filter is not None:
            if chart.rank not in score_filter.levels:
                continue
            if not score_filter.difficulty.contains(chart.difficulty):
                continue
        current = record_map.get((chart.song_id, chart.rank))
        rating = "NEW" if current is None else ("PHI" if current.rating == "phi" else current.rating.upper())
        if score_filter is not None and rating not in score_filter.ratings:
            continue
        target_rks = max(floor_rks, current.rks if current else 0.0) + min_up
        target_acc = target_acc_for_rks(target_rks, chart.difficulty)
        if target_acc is None:
            if phi_floor is not None and chart.difficulty > phi_floor + min_up:
                target_acc = 100.0
            else:
                continue
        if target_acc > 100:
            continue
        entry = SuggestEntry(
            chart=chart,
            current=current,
            target_acc=target_acc,
            target_rks=target_rks,
            avg_acc=avg_lookup.get((chart.song_id, chart.rank), 0.0),
        )
        suggestions[_suggest_bucket(target_acc)].append(entry)

    result: list[SuggestEntry] = []
    for index in range(6):
        result.extend(sorted(suggestions[index], key=_suggest_sort_key)[:per_group_limit])
    return result


def charts_for_table(catalog: SongCatalog, difficulty: int | float, changes: list[dict[str, str]] | None = None) -> list[ChartEntry]:
    low = float(difficulty)
    high = low + 0.9 if float(difficulty).is_integer() else low
    rng = RangeFilter(low, high)
    if changes is not None:
        return _charts_for_table_changes(catalog, changes, rng)
    return [entry for entry in all_chart_entries(catalog) if rng.contains(entry.difficulty)]


def _charts_for_table_changes(catalog: SongCatalog, changes: list[dict[str, str]], rng: RangeFilter) -> list[ChartEntry]:
    entries: list[ChartEntry] = []
    for row in changes:
        song_id = normalize_song_id(str(row.get("id") or ""))
        if not song_id:
            continue
        song = catalog.get(song_id)
        title = song.title if song is not None else song_id
        for rank in LEVELS:
            raw_difficulty = row.get(rank)
            if raw_difficulty is None or str(raw_difficulty).strip() == "":
                continue
            try:
                difficulty = float(raw_difficulty)
            except (TypeError, ValueError):
                continue
            if not rng.contains(difficulty):
                continue
            chart = song.charts.get(rank) if song is not None else None
            entries.append(ChartEntry(
                song_id=song_id,
                song_title=title,
                rank=rank,
                difficulty=difficulty,
                difficulty_text=f"{difficulty:.1f}",
                combo=chart.combo if chart is not None else None,
            ))
    return sorted(entries, key=lambda item: (item.difficulty, item.rank, item.song_title))


def random_challenge(catalog: SongCatalog, args: str, *, rng: random.Random | None = None) -> tuple[int, list[ChartEntry]] | None:
    rng = rng or random.Random()
    entries = all_chart_entries(catalog)
    max_diff = max((entry.difficulty for entry in entries), default=18.0)
    target_args, chart_args = _split_challenge_args(args)
    parsed_range = parse_range(target_args, default=(20.0, 45.0), max_value=51.0, int_bucket=True)
    target_levels = parse_levels(target_args)
    chart_range = parse_range(chart_args, default=(0.0, max_diff), max_value=max_diff, int_bucket=True)
    chart_levels = parse_levels(chart_args)
    charts = [
        entry
        for entry in entries
        if entry.rank in target_levels
        and entry.rank in chart_levels
        and chart_range.contains(entry.difficulty)
    ]
    by_floor: dict[int, list[ChartEntry]] = {}
    for chart in charts:
        by_floor.setdefault(int(math.floor(chart.difficulty)), []).append(chart)
    targets = list(range(max(1, int(parsed_range.low)), int(parsed_range.high) + 1))
    rng.shuffle(targets)
    for target in targets:
        for _ in range(1500):
            parts = _random_three_parts(target, by_floor.keys(), rng)
            if not parts:
                continue
            selected: list[ChartEntry] = []
            used: set[tuple[str, str]] = set()
            ok = True
            for part in parts:
                candidates = by_floor.get(part, [])
                if not candidates:
                    ok = False
                    break
                candidate = rng.choice(candidates)
                key = (candidate.song_id, candidate.rank)
                if key in used:
                    ok = False
                    break
                used.add(key)
                selected.append(candidate)
            if ok and len(selected) == 3:
                return target, selected
    return None


def _split_challenge_args(args: str) -> tuple[str, str]:
    match = re.search(r"[\(（]([^()（）]*)[\)）]", args)
    if match is None:
        return args, ""
    outer = f"{args[:match.start()]} {args[match.end():]}".strip()
    return outer, match.group(1).strip()


def _random_three_parts(target: int, available: Iterable[int], rng: random.Random) -> list[int] | None:
    values = sorted(set(available))
    if not values:
        return None
    for _ in range(80):
        a = rng.choice(values)
        b = rng.choice(values)
        c = target - a - b
        if c in values:
            return [a, b, c]
    return None


def _is_one_good_like(record: ScoreRecord, chart: ChartEntry | None) -> bool:
    if record.acc >= 100:
        return False
    if chart and chart.combo:
        target = 900000 * (1 - (0.35 / chart.combo)) + 100000
        return abs(record.score - target) <= 2
    return record.score >= 999_990


def _fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _min_up_rks(rks: float) -> float:
    value = math.floor(rks * 100) / 100 + 0.005 - rks
    return value + 0.01 if value < 0 else value


def _suggest_bucket(acc: float) -> int:
    if acc < 98.5:
        return 0
    if acc < 99:
        return 1
    if acc < 99.5:
        return 2
    if acc < 99.7:
        return 3
    if acc < 99.85:
        return 4
    return 5


def _suggest_sort_key(entry: SuggestEntry) -> tuple[float, float, str, int]:
    rank_order = {rank: index for index, rank in enumerate(LEVELS)}
    delta = entry.chart.difficulty * 100 * (entry.target_acc - entry.avg_acc)
    return (delta, -entry.chart.difficulty, entry.chart.song_title, rank_order.get(entry.chart.rank, 99))


def _record_song_ids(snapshot: SaveSnapshot) -> set[str]:
    raw_records = snapshot.raw.get("gameRecord")
    if not isinstance(raw_records, dict):
        return set()
    return {normalize_song_id(str(song_id)) for song_id in raw_records}
