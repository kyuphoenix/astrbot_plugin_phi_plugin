from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ..data.loader import SongCatalog, normalize_song_id
from ..models import ProgressDay, ProgressScoreChange, SaveSnapshot, ScoreRecord, UpdateProgressSummary
from .b30 import iter_score_records, rating_from_score, rks_from_acc

HISTORY_VERSION = 3
MAX_DAYS = 4
MAX_PER_DAY = 4
MAX_TOTAL = 12


def update_progress_history(
    snapshot: SaveSnapshot,
    catalog: SongCatalog,
    history: dict[str, Any],
    *,
    previous_snapshot: SaveSnapshot | None = None,
) -> tuple[dict[str, Any], UpdateProgressSummary]:
    normalized = normalize_history(history)
    before = deepcopy(normalized)
    was_empty = _history_is_empty(normalized)

    modified_dt = extract_modified_datetime(snapshot.raw)
    modified_iso = _to_iso(modified_dt)
    records = iter_score_records(snapshot, catalog)

    for record in records:
        _insert_score_record(normalized, record, modified_iso)

    _append_series_value(normalized, "rks", modified_dt, snapshot.ranking_score)
    money = extract_money(snapshot.raw)
    if money is not None:
        _append_series_value(normalized, "data", modified_dt, money)
    if snapshot.challenge_mode_rank is not None:
        _append_series_value(normalized, "challengeModeRank", modified_dt, snapshot.challenge_mode_rank)

    recent_days = recent_progress_days(normalized, catalog)
    modified_text = format_datetime(modified_dt)
    current_update_count = _count_scores_on_date(normalized, modified_text)
    shown_changes = sum(len(day.changes) for day in recent_days)

    rks_delta = _rks_delta(snapshot, previous_snapshot, before, modified_dt)
    data_delta = _data_delta(money, previous_snapshot, before, modified_dt)
    challenge_delta = _challenge_delta(snapshot, previous_snapshot, before, modified_dt)

    return normalized, UpdateProgressSummary(
        player_id=snapshot.player_id,
        player_name=snapshot.player_name,
        ranking_score=snapshot.ranking_score,
        challenge_mode_rank=snapshot.challenge_mode_rank,
        modified_at=modified_text,
        total_records=len(records),
        current_update_count=current_update_count,
        shown_changes=shown_changes,
        recent_days=recent_days,
        rks_delta=rks_delta,
        challenge_delta=challenge_delta,
        data_money=money,
        data_delta=data_delta,
        is_first_record=was_empty,
    )


def normalize_history(history: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(history, dict):
        history = {}
    score_history = history.get("scoreHistory")
    if not isinstance(score_history, dict):
        score_history = {}
    return {
        "version": HISTORY_VERSION,
        "scoreHistory": score_history,
        "rks": _coerce_series(history.get("rks")),
        "data": _coerce_series(history.get("data")),
        "challengeModeRank": _coerce_series(history.get("challengeModeRank")),
    }


def merge_histories(primary: dict[str, Any] | None, secondary: dict[str, Any] | None) -> dict[str, Any]:
    merged = normalize_history(primary)
    extra = normalize_history(secondary)
    _merge_series(merged["rks"], extra["rks"])
    _merge_series(merged["data"], extra["data"])
    _merge_series(merged["challengeModeRank"], extra["challengeModeRank"])

    target_scores = merged["scoreHistory"]
    for song_id, level_map in extra["scoreHistory"].items():
        if not isinstance(level_map, dict):
            continue
        target_level_map = target_scores.setdefault(song_id, {})
        if not isinstance(target_level_map, dict):
            target_level_map = {}
            target_scores[song_id] = target_level_map
        for rank, items in level_map.items():
            if not isinstance(items, list):
                continue
            target_items = target_level_map.setdefault(rank, [])
            if not isinstance(target_items, list):
                target_items = []
                target_level_map[rank] = target_items
            for item in items:
                opened = _open_score_item(item)
                if opened is None:
                    continue
                if not any(existing and _same_opened_score(existing, opened) for existing in (_open_score_item(raw) for raw in target_items)):
                    target_items.append([f"{opened['acc']:.4f}", int(opened["score"]), _to_iso(opened["date"]), bool(opened["fc"])])
            target_items.sort(key=lambda raw: _timestamp((_open_score_item(raw) or {"date": datetime.min})["date"]))
            _dedupe_score_items(target_items)
    return merged


def recent_progress_days(
    history: dict[str, Any],
    catalog: SongCatalog,
    *,
    max_days: int = MAX_DAYS,
    max_per_day: int = MAX_PER_DAY,
    max_total: int = MAX_TOTAL,
) -> list[ProgressDay]:
    groups: dict[str, dict[str, Any]] = {}
    score_history = history.get("scoreHistory") if isinstance(history.get("scoreHistory"), dict) else {}
    for raw_song_id, level_map in score_history.items():
        song_id = normalize_song_id(str(raw_song_id))
        song = catalog.get(song_id)
        if not isinstance(level_map, dict):
            continue
        for rank, raw_items in level_map.items():
            items = [_open_score_item(item) for item in raw_items if _open_score_item(item) is not None]
            items.sort(key=lambda item: _timestamp(item["date"]))
            previous: dict[str, Any] | None = None
            for item in items:
                date_text = format_datetime(item["date"])
                group = groups.setdefault(date_text, {"date": item["date"], "count": 0, "changes": []})
                group["count"] += 1
                change = _score_change(song_id, str(rank), item, previous, song, catalog)
                if change is not None:
                    group["changes"].append(change)
                previous = item

    ordered = sorted(groups.items(), key=lambda pair: _timestamp(pair[1]["date"]), reverse=True)
    days: list[ProgressDay] = []
    shown = 0
    for date_text, data in ordered[:max_days]:
        changes = sorted(
            data["changes"],
            key=lambda item: (item.rks_new, _score_delta(item), item.acc_new),
            reverse=True,
        )
        allowed = max(0, min(max_per_day, max_total - shown))
        picked = changes[:allowed]
        shown += len(picked)
        days.append(ProgressDay(date=date_text, update_count=int(data["count"]), changes=picked))
        if shown >= max_total:
            break
    return days


def extract_modified_datetime(raw: dict[str, Any]) -> datetime:
    save_info = raw.get("saveInfo") if isinstance(raw.get("saveInfo"), dict) else {}
    summary = save_info.get("summary") if isinstance(save_info.get("summary"), dict) else {}
    candidates = [
        save_info.get("modifiedAt"),
        save_info.get("updatedAt"),
        summary.get("updatedAt"),
        raw.get("modifiedAt"),
        raw.get("updatedAt"),
    ]
    for value in candidates:
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return _normalize_datetime(datetime.now(timezone.utc))


def extract_money(raw: dict[str, Any]) -> list[int] | None:
    game_progress = raw.get("gameProgress")
    money = game_progress.get("money") if isinstance(game_progress, dict) else raw.get("money")
    if not isinstance(money, list):
        return None
    values: list[int] = []
    for item in money[:5]:
        try:
            values.append(int(item))
        except (TypeError, ValueError):
            values.append(0)
    while len(values) < 5:
        values.append(0)
    return values


def money_to_kib(money: list[int] | None) -> int | None:
    if money is None:
        return None
    return sum(int(value) * (1024 ** index) for index, value in enumerate(money[:5]))


def format_datetime(value: datetime) -> str:
    return value.strftime("%Y/%m/%d %H:%M:%S")


def _insert_score_record(history: dict[str, Any], record: ScoreRecord, date_iso: str) -> bool:
    score_history = history.setdefault("scoreHistory", {})
    song_map = score_history.get(record.song_id)
    if not isinstance(song_map, dict):
        song_map = {}
        score_history[record.song_id] = song_map
    items = song_map.get(record.rank)
    if not isinstance(items, list):
        items = []
        song_map[record.rank] = items
    new_item = [f"{record.acc:.4f}", int(record.score), date_iso, bool(record.fc)]
    opened = [_open_score_item(item) for item in items]
    for item in opened:
        if item and _same_score_values(item, new_item):
            return False
    items.append(new_item)
    items.sort(key=lambda item: _timestamp((_open_score_item(item) or {"date": datetime.min})["date"]))
    _dedupe_score_items(items)
    return True


def _dedupe_score_items(items: list[Any]) -> None:
    index = 1
    while index < len(items):
        previous = _open_score_item(items[index - 1])
        current = _open_score_item(items[index])
        if previous and current and _same_opened_score(previous, current):
            items.pop(index)
            continue
        index += 1


def _append_series_value(history: dict[str, Any], key: str, date: datetime, value: Any) -> bool:
    series = history.setdefault(key, [])
    if not isinstance(series, list):
        series = []
        history[key] = series
    date_iso = _to_iso(date)
    for item in series:
        if isinstance(item, dict) and format_datetime(_parse_datetime(item.get("date")) or date) == format_datetime(date):
            item["value"] = value
            item["date"] = date_iso
            return False
    if series:
        latest = max(series, key=lambda item: _timestamp(_parse_datetime(item.get("date")) or datetime.min) if isinstance(item, dict) else 0)
        if isinstance(latest, dict) and _series_value_equal(latest.get("value"), value):
            return False
    series.append({"date": date_iso, "value": value})
    series.sort(key=lambda item: _timestamp(_parse_datetime(item.get("date")) or datetime.min) if isinstance(item, dict) else 0)
    return True


def _score_change(
    song_id: str,
    rank: str,
    item: dict[str, Any],
    previous: dict[str, Any] | None,
    song: Any,
    catalog: SongCatalog,
) -> ProgressScoreChange | None:
    title = getattr(song, "title", "") or song_id
    difficulty = 0.0
    if song and rank in song.charts and song.charts[rank].difficulty is not None:
        difficulty = float(song.charts[rank].difficulty)
    rks_new = rks_from_acc(float(item["acc"]), difficulty)
    rks_old = rks_from_acc(float(previous["acc"]), difficulty) if previous else None
    return ProgressScoreChange(
        song_id=song_id,
        song_title=title,
        rank=rank,
        date=format_datetime(item["date"]),
        score_new=int(item["score"]),
        acc_new=float(item["acc"]),
        fc_new=bool(item["fc"]),
        rating_new=rating_from_score(int(item["score"]), bool(item["fc"])),
        rks_new=rks_new,
        score_old=int(previous["score"]) if previous else None,
        acc_old=float(previous["acc"]) if previous else None,
        fc_old=bool(previous["fc"]) if previous else None,
        rks_old=rks_old,
    )


def _open_score_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, list | tuple) or len(item) < 4:
        return None
    date = _parse_datetime(item[2])
    if date is None:
        return None
    try:
        acc = round(float(item[0]), 4)
        score = int(item[1])
    except (TypeError, ValueError):
        return None
    return {"acc": acc, "score": score, "date": date, "fc": bool(item[3])}


def _same_score_values(opened: dict[str, Any], raw_item: list[Any]) -> bool:
    try:
        acc = round(float(raw_item[0]), 4)
        score = int(raw_item[1])
    except (TypeError, ValueError):
        return False
    return opened["score"] == score and opened["acc"] == acc and opened["fc"] == bool(raw_item[3])


def _same_opened_score(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left["score"] == right["score"] and left["acc"] == right["acc"] and left["fc"] == right["fc"]


def _count_scores_on_date(history: dict[str, Any], date_text: str) -> int:
    count = 0
    score_history = history.get("scoreHistory") if isinstance(history.get("scoreHistory"), dict) else {}
    for level_map in score_history.values():
        if not isinstance(level_map, dict):
            continue
        for raw_items in level_map.values():
            if not isinstance(raw_items, list):
                continue
            for raw_item in raw_items:
                item = _open_score_item(raw_item)
                if item and format_datetime(item["date"]) == date_text:
                    count += 1
    return count


def _history_is_empty(history: dict[str, Any]) -> bool:
    score_history = history.get("scoreHistory") if isinstance(history.get("scoreHistory"), dict) else {}
    if any(isinstance(level_map, dict) and any(level_map.values()) for level_map in score_history.values()):
        return False
    return not history.get("rks") and not history.get("data") and not history.get("challengeModeRank")


def _rks_delta(
    snapshot: SaveSnapshot,
    previous_snapshot: SaveSnapshot | None,
    history_before: dict[str, Any],
    modified_dt: datetime,
) -> float | None:
    if previous_snapshot is not None:
        return snapshot.ranking_score - previous_snapshot.ranking_score
    previous = _latest_series_before(history_before.get("rks"), modified_dt)
    if isinstance(previous, (int, float)):
        return snapshot.ranking_score - float(previous)
    return None


def _data_delta(
    money: list[int] | None,
    previous_snapshot: SaveSnapshot | None,
    history_before: dict[str, Any],
    modified_dt: datetime,
) -> int | None:
    current = money_to_kib(money)
    if current is None:
        return None
    previous_money = extract_money(previous_snapshot.raw) if previous_snapshot is not None else None
    previous = money_to_kib(previous_money)
    if previous is None:
        before_value = _latest_series_before(history_before.get("data"), modified_dt)
        previous = money_to_kib(before_value) if isinstance(before_value, list) else None
    if previous is None:
        return None
    return current - previous


def _challenge_delta(
    snapshot: SaveSnapshot,
    previous_snapshot: SaveSnapshot | None,
    history_before: dict[str, Any],
    modified_dt: datetime,
) -> int | float | None:
    current = _as_number(snapshot.challenge_mode_rank)
    if current is None:
        return None
    previous = _as_number(previous_snapshot.challenge_mode_rank) if previous_snapshot is not None else None
    if previous is None:
        previous = _as_number(_latest_series_before(history_before.get("challengeModeRank"), modified_dt))
    if previous is None:
        return None
    return current - previous


def _latest_series_before(series: Any, date: datetime) -> Any:
    if not isinstance(series, list):
        return None
    latest_date: datetime | None = None
    latest_value: Any = None
    for item in series:
        if not isinstance(item, dict):
            continue
        item_date = _parse_datetime(item.get("date"))
        if item_date is None or item_date >= date:
            continue
        if latest_date is None or item_date > latest_date:
            latest_date = item_date
            latest_value = item.get("value")
    return latest_value


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    if isinstance(value, dict):
        for key in ("iso", "date", "value"):
            parsed = _parse_datetime(value.get(key))
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:
            raw /= 1000
        try:
            return _normalize_datetime(datetime.fromtimestamp(raw, tz=timezone.utc))
        except (OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _normalize_datetime(datetime.fromisoformat(text))
    except ValueError:
        pass
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return _normalize_datetime(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return None


def _to_iso(value: datetime) -> str:
    return value.isoformat()


def _coerce_series(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and "date" in item and "value" in item:
            result.append({"date": _to_iso(_parse_datetime(item["date"]) or _normalize_datetime(datetime.now(timezone.utc))), "value": item["value"]})
    result.sort(key=lambda item: _timestamp(_parse_datetime(item.get("date")) or datetime.min))
    return result


def _merge_series(target: list[dict[str, Any]], extra: list[dict[str, Any]]) -> None:
    for item in extra:
        item_date = _parse_datetime(item.get("date"))
        if item_date is None:
            continue
        item_value = item.get("value")
        duplicate = False
        for existing in target:
            existing_date = _parse_datetime(existing.get("date"))
            if existing_date is None:
                continue
            if format_datetime(existing_date) == format_datetime(item_date) and _series_value_equal(existing.get("value"), item_value):
                duplicate = True
                break
        if not duplicate:
            target.append({"date": _to_iso(item_date), "value": item_value})
    target.sort(key=lambda item: _timestamp(_parse_datetime(item.get("date")) or datetime.min))


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _timestamp(value: datetime) -> float:
    try:
        return value.timestamp()
    except (OSError, ValueError):
        return 0.0


def _series_value_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        try:
            return abs(float(left) - float(right)) < 1e-9
        except (TypeError, ValueError):
            return False
    return left == right


def _score_delta(change: ProgressScoreChange) -> int:
    if change.score_old is None:
        return change.score_new
    return change.score_new - change.score_old


def _as_number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number
