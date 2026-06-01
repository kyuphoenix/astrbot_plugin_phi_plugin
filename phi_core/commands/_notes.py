from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, time
from typing import Any

from .common import CommandContext
from ..data.illustrations import random_background_source
from ..models import LEVELS, SaveSnapshot, ScoreRecord
from ..query import iter_score_records, summarize_level_scores
from ..query.filters import ScoreFilter, RangeFilter
from ..render import original
from ..save import SaveNotAvailable


def today_key(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def day_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now()
    return datetime.combine(current.date(), time.min)


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(tzinfo=None)
        except ValueError:
            pass
    return None


def load_notes(ctx: CommandContext, user_id: str) -> dict[str, Any]:
    notes = ctx.store.load_notes(user_id)
    if notes.get("theme") == "common":
        notes["theme"] = "default"
    return notes


def save_notes(ctx: CommandContext, user_id: str, notes: dict[str, Any]) -> None:
    ctx.store.save_notes(user_id, notes)


def format_time(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def hello_message(now: datetime | None = None) -> str:
    current = now or datetime.now()
    clock = current.strftime("%H:%M:%S")
    hour = current.hour + current.minute / 60
    if hour < 6:
        return f"现在是 {clock}，夜深了，注意休息哦。"
    if hour < 11.5:
        return f"现在是 {clock}，早安。"
    if hour < 13:
        return f"现在是 {clock}，午好。"
    if hour < 18.5:
        return f"现在是 {clock}，下午好。"
    if hour < 23:
        return f"现在是 {clock}，晚上好。"
    return f"现在是 {clock}，夜深了，注意休息哦。"


def task_finished_by_record(task: dict[str, Any], record: ScoreRecord | None) -> bool:
    if record is None:
        return False
    request = task.get("request") if isinstance(task.get("request"), dict) else {}
    task_type = str(request.get("type") or "acc").casefold()
    value = _as_float(request.get("value"))
    if task_type == "score":
        return record.score >= int(value)
    return record.acc >= value


def apply_task_rewards(ctx: CommandContext, user_id: str, snapshot: SaveSnapshot | None, notes: dict[str, Any]) -> int:
    tasks = notes.get("task")
    if not snapshot or not isinstance(tasks, list) or not tasks:
        return 0
    records = {(record.song_id, record.rank): record for record in iter_score_records(snapshot, ctx.catalog)}
    added = 0
    changed = False
    for task in tasks:
        if not isinstance(task, dict) or task.get("finished"):
            continue
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        song_id = str(task.get("song") or "")
        rank = str(request.get("rank") or "").upper()
        if not song_id or rank not in LEVELS:
            continue
        record = records.get((song_id, rank))
        if task_finished_by_record(task, record):
            reward = max(0, _as_int(task.get("reward")))
            task["finished"] = True
            notes["money"] = max(0, _as_int(notes.get("money"))) + reward
            added += reward
            changed = True
    if changed:
        save_notes(ctx, user_id, notes)
    return added


async def maybe_refresh_daily_tasks(
    ctx: CommandContext,
    user_id: str,
    snapshot: SaveSnapshot | None,
    notes: dict[str, Any],
    *,
    force: bool = False,
    preserve_finished: bool = False,
) -> bool:
    if snapshot is None:
        return False
    last_task = parse_datetime(notes.get("task_time"))
    should_refresh = force or last_task is None or last_task < day_start()
    if not should_refresh:
        return False
    old_tasks = notes.get("task") if preserve_finished and isinstance(notes.get("task"), list) else []
    notes["task_time"] = datetime.now().isoformat()
    notes["task"] = await generate_tasks(ctx, snapshot, old_tasks)
    save_notes(ctx, user_id, notes)
    return True


async def generate_tasks(ctx: CommandContext, snapshot: SaveSnapshot, old_tasks: list[Any] | None = None) -> list[dict[str, Any] | None]:
    existing = list(old_tasks or [])
    result: list[dict[str, Any] | None] = [None, None, None, None, None]
    for index, task in enumerate(existing[:5]):
        if isinstance(task, dict) and task.get("finished"):
            result[index] = task

    records = iter_score_records(snapshot, ctx.catalog)
    record_map = {(record.song_id, record.rank): record for record in records}
    com_rks = _computed_rks(records, snapshot.ranking_score)
    api_tasks = await _api_average_tasks(ctx, snapshot, record_map, com_rks)
    rng = random.Random()

    for index in range(5):
        if result[index] is not None:
            continue
        task = _pop_api_task(api_tasks, rng) or _random_local_task(ctx, snapshot, record_map, com_rks, index, rng)
        result[index] = task
    for task in result:
        if isinstance(task, dict):
            task.pop("_sort", None)
    return result


def build_sign_panel_data(
    ctx: CommandContext,
    user_id: str,
    snapshot: SaveSnapshot | None,
    notes: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now()
    fortune = _fortune_data(ctx, user_id)
    edge_rate = _edge_rate(ctx, snapshot)
    calendar = _calendar(now.year, now.month, set(notes.get("sign_history", [])), today_key(now))
    notice = _consume_notice(ctx, user_id, notes)
    tasks = _daily_task_rows(ctx, snapshot, notes)
    return {
        "PlayerId": snapshot.player_id if snapshot else "游客玩家",
        "Rks": f"{snapshot.ranking_score:.4f}" if snapshot else "0.0000",
        "Date": format_time(now),
        "ChallengeMode": _challenge_mode(snapshot),
        "ChallengeModeRank": _challenge_rank(snapshot),
        "avatar": _avatar(snapshot),
        "background": _random_sign_background(ctx),
        "Notes": _as_int(notes.get("money")),
        "signDays": len(notes.get("sign_history", [])) if isinstance(notes.get("sign_history"), list) else 0,
        "lucky": fortune["lucky"],
        "good": fortune["good"],
        "bad": fortune["bad"],
        "quote": fortune["quote"],
        "edgeRate": edge_rate,
        "dailyTasks": tasks,
        "calendar": calendar,
        "notice": notice,
        "theme": str(notes.get("theme") or "default"),
    }


def build_tasks_panel_data(
    ctx: CommandContext,
    user_id: str,
    snapshot: SaveSnapshot,
    notes: dict[str, Any],
    *,
    change_notes: int = 0,
    tips: str = "",
) -> dict[str, Any]:
    data = build_sign_panel_data(ctx, user_id, snapshot, notes)
    data["task"] = _classic_task_rows(ctx, snapshot, notes)
    data["task_ans"] = "完成任务可获得 Notes；每日首次刷新免费。"
    data["task_ans1"] = "红色为未完成，金色为已完成。"
    data["change_notes"] = _signed_notes(change_notes) if change_notes else ""
    data["tips"] = tips
    return data


def _fortune_data(ctx: CommandContext, user_id: str) -> dict[str, Any]:
    today = today_key()
    cached = ctx.store.get_jrrp_cache(user_id, today)
    if cached is None:
        try:
            from .jrrp import _make_jrrp

            cached = _make_jrrp(ctx.paths.info, rng=random.Random())
        except Exception:
            cached = [0, 0, "打歌", "收歌", "推分", "查分", "熬夜", "爆准", "手癖", "摸鱼"]
        ctx.store.save_jrrp_cache(user_id, today, cached)
    sentences = _load_sentences(ctx)
    sentence_index = _as_int(cached[1] if len(cached) > 1 else 0)
    sentence = sentences[sentence_index % len(sentences)] if sentences else {}
    quote = str(sentence.get("hitokoto") or sentence.get("text") or "") if isinstance(sentence, dict) else str(sentence or "")
    return {
        "lucky": _as_int(cached[0] if cached else 0),
        "good": [str(item) for item in cached[2:6]],
        "bad": [str(item) for item in cached[6:10]],
        "quote": quote,
    }


def _load_sentences(ctx: CommandContext) -> list[Any]:
    path = ctx.paths.info / "sentences.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _edge_rate(ctx: CommandContext, snapshot: SaveSnapshot | None) -> dict[str, dict[str, str]]:
    result = {level: {"unlock": "0%", "fc": "0%", "phi": "0%"} for level in LEVELS}
    if snapshot is None:
        return result
    full_filter = ScoreFilter(
        difficulty=RangeFilter(0.0, max((chart.difficulty or 0.0 for song in ctx.catalog.all_songs() for chart in song.charts.values()), default=18.0)),
        acc=RangeFilter(0.0, 100.0),
        levels=set(LEVELS),
        ratings={"NEW", "F", "C", "B", "A", "S", "V", "FC", "PHI"},
    )
    summary = summarize_level_scores(snapshot, ctx.catalog, full_filter)
    total_by_level = summary.rank_counts
    records_by_level: dict[str, list[ScoreRecord]] = {level: [] for level in LEVELS}
    for record in iter_score_records(snapshot, ctx.catalog):
        if record.rank in records_by_level:
            records_by_level[record.rank].append(record)
    for level in LEVELS:
        total = max(1, total_by_level.get(level, 0))
        played = len(records_by_level[level])
        fc = sum(1 for record in records_by_level[level] if record.fc or record.rating == "phi")
        phi = sum(1 for record in records_by_level[level] if record.rating == "phi")
        result[level] = {
            "unlock": _percent_text(played, total),
            "fc": _percent_text(fc, total),
            "phi": _percent_text(phi, total),
        }
    return result


def _calendar(year: int, month: int, sign_history: set[str], today: str) -> dict[str, Any]:
    import calendar

    first_weekday, days_in_month = calendar.monthrange(year, month)
    day = 1
    weeks: list[list[dict[str, Any]]] = []
    for week_index in range(6):
        week: list[dict[str, Any]] = []
        for index in range(7):
            if (week_index == 0 and index < first_weekday) or day > days_in_month:
                week.append({"empty": True})
                continue
            key = f"{year}-{month:02d}-{day:02d}"
            week.append({
                "empty": False,
                "day": day,
                "signed": key in sign_history,
                "today": key == today,
            })
            day += 1
        weeks.append(week)
    return {
        "title": f"{year} 年 {month} 月",
        "weekdays": ["一", "二", "三", "四", "五", "六", "日"],
        "weeks": weeks,
    }


def _consume_notice(ctx: CommandContext, user_id: str, notes: dict[str, Any]) -> dict[str, Any] | None:
    path = ctx.paths.info / "notice.json"
    if not path.exists():
        return None
    try:
        notice = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    if not isinstance(notice, dict):
        return None
    code = _as_int(notice.get("code"))
    if code <= _as_int(notes.get("noticeCode")):
        return None
    notes["noticeCode"] = code
    save_notes(ctx, user_id, notes)
    content = notice.get("content")
    if isinstance(content, str):
        content = content.replace("<br/>", "\n").replace("<br>", "\n").splitlines()
    elif not isinstance(content, list):
        content = []
    return {
        "title": str(notice.get("title") or "Notice"),
        "content": [str(item) for item in content][:5],
    }


def _daily_task_rows(ctx: CommandContext, snapshot: SaveSnapshot | None, notes: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tasks = notes.get("task") if isinstance(notes.get("task"), list) else []
    for index, task in enumerate(tasks[:5], 1):
        if not isinstance(task, dict):
            continue
        song = ctx.catalog.get(str(task.get("song") or ""))
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        rank = str(request.get("rank") or "")
        difficulty = ""
        if song and rank in song.charts and song.charts[rank].difficulty is not None:
            difficulty = f"{song.charts[rank].difficulty:.1f}"
        meta = f"{rank} {difficulty} · {str(request.get('type') or 'acc').upper()} {request.get('value', '')} · +{_as_int(task.get('reward'))} Notes"
        rows.append({
            "index": f"{index:02d}",
            "song": song.title if song else str(task.get("song") or "UNKNOWN"),
            "illustration": _task_illustration(ctx, str(task.get("song") or "")),
            "meta": meta,
            "finished": bool(task.get("finished")),
        })
    return rows


def _classic_task_rows(ctx: CommandContext, snapshot: SaveSnapshot | None, notes: dict[str, Any]) -> list[dict[str, Any] | None]:
    rows: list[dict[str, Any] | None] = []
    tasks = notes.get("task") if isinstance(notes.get("task"), list) else []
    for task in tasks[:5]:
        if not isinstance(task, dict):
            rows.append(None)
            continue
        song = ctx.catalog.get(str(task.get("song") or ""))
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        rows.append({
            "song": song.title if song else str(task.get("song") or "UNKNOWN"),
            "illustration": _task_illustration(ctx, str(task.get("song") or "")),
            "reward": _as_int(task.get("reward")),
            "finished": bool(task.get("finished")),
            "request": {
                "rank": str(request.get("rank") or ""),
                "type": str(request.get("type") or "acc"),
                "value": request.get("value", ""),
            },
        })
    return rows


async def _api_average_tasks(
    ctx: CommandContext,
    snapshot: SaveSnapshot,
    record_map: dict[tuple[str, str], ScoreRecord],
    com_rks: float,
) -> list[dict[str, Any]]:
    song_ids = [song.id_with_suffix for song in ctx.catalog.all_songs()]
    min_rks = math.floor((com_rks - 0.05) / 0.05) * 0.05
    max_rks = math.floor((com_rks + 0.05) / 0.05) * 0.05
    try:
        data = await ctx.client.fetch_all_song_acc_avg(song_ids, min_rks=min_rks, max_rks=max_rks, b30=True)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        return []
    tasks: list[dict[str, Any]] = []
    for song in ctx.catalog.all_songs():
        raw_song = _lookup_song_data(data, song.id)
        if not isinstance(raw_song, dict):
            continue
        for rank, chart in song.charts.items():
            if rank not in LEVELS or chart.difficulty is None:
                continue
            raw_rank = raw_song.get(rank)
            if not isinstance(raw_rank, dict):
                continue
            target = _as_float(raw_rank.get("accAvg"))
            current = record_map.get((song.id, rank))
            old_acc = current.acc if current else 0.0
            if target <= old_acc or target < 95:
                continue
            tasks.append(_task(song.id, rank, "acc", round(min(target, 100.0), 2), com_rks, chart.difficulty, old_acc))
    return sorted(tasks, key=lambda item: float(item.get("_sort", 0.0)), reverse=True)


def _lookup_song_data(data: dict[str, Any], song_id: str) -> Any:
    for candidate in (song_id, f"{song_id}.0", song_id.removesuffix(".0")):
        if candidate in data:
            return data[candidate]
    return None


def _pop_api_task(tasks: list[dict[str, Any]], rng: random.Random) -> dict[str, Any] | None:
    if not tasks:
        return None
    index = rng.randrange(min(len(tasks), 20))
    task = tasks.pop(index)
    task.pop("_sort", None)
    return task


def _random_local_task(
    ctx: CommandContext,
    snapshot: SaveSnapshot,
    record_map: dict[tuple[str, str], ScoreRecord],
    com_rks: float,
    slot: int,
    rng: random.Random,
) -> dict[str, Any] | None:
    rank_lines = _rank_lines(snapshot.ranking_score)
    candidates: list[tuple[Any, str, float, ScoreRecord | None]] = []
    low = rank_lines[slot - 1] if slot > 0 else -100.0
    high = rank_lines[slot] if slot < len(rank_lines) else 18.0
    for song in ctx.catalog.all_songs():
        for rank, chart in song.charts.items():
            if rank not in LEVELS or chart.difficulty is None:
                continue
            record = record_map.get((song.id, rank))
            if record and record.acc >= 100:
                continue
            if low <= chart.difficulty < high:
                candidates.append((song, rank, chart.difficulty, record))
    if not candidates:
        for song in ctx.catalog.all_songs():
            for rank, chart in song.charts.items():
                if rank in LEVELS and chart.difficulty is not None:
                    record = record_map.get((song.id, rank))
                    if not record or record.acc < 100:
                        candidates.append((song, rank, chart.difficulty, record))
    if not candidates:
        return None
    song, rank, difficulty, record = rng.choice(candidates)
    old_acc = record.acc if record else 0.0
    target = min(100.0, round(_ease_in_sine(rng.random(), min(old_acc + 0.01, 100.0), 100.0 - min(old_acc + 0.01, 100.0), 1.0), 2))
    return _task(song.id, rank, "acc", target, com_rks, difficulty, old_acc)


def _rank_lines(rks: float) -> list[float]:
    if rks < 15:
        return [rks - 1.0, rks - 0.5, rks, rks + 1.0, 18.0]
    if rks < 16:
        return [rks - 1.5, rks - 0.3, rks, rks + 0.5, 18.0]
    return [rks - 2.0, rks - 1.0, rks - 0.5, rks, 18.0]


def _task(song_id: str, rank: str, task_type: str, value: float, com_rks: float, difficulty: float, old_acc: float) -> dict[str, Any]:
    reward = _reward(com_rks, difficulty, value, old_acc)
    return {
        "song": song_id,
        "reward": reward,
        "finished": False,
        "request": {
            "rank": rank,
            "type": task_type,
            "value": round(value, 2),
        },
        "_sort": value,
    }


def _reward(rks: float, difficulty: float, value: float, old_acc: float) -> int:
    p1 = math.ceil(min(max(difficulty - rks, 0.0) * 20.0, 50.0))
    p2 = math.ceil(min(max(value - old_acc, 0.0) * 5.0, 20.0))
    p3 = math.ceil((max(value - 95.0, 0.0) / 5.0) ** 3 * 30.0)
    return max(1, p1 + p2 + p3)


def _computed_rks(records: list[ScoreRecord], fallback: float) -> float:
    if not records:
        return fallback
    phi_records = sorted((record for record in records if record.acc >= 100), key=lambda item: item.rks, reverse=True)[:3]
    best_records = sorted(records, key=lambda item: item.rks, reverse=True)[:27]
    selected = [*phi_records, *best_records]
    return sum(record.rks for record in selected) / 30.0 if selected else fallback


def _ease_in_sine(t: float, b: float, c: float, d: float) -> float:
    return -c * math.cos(t / d * (math.pi / 2)) + c + b


def _task_illustration(ctx: CommandContext, song_id: str) -> str:
    song = ctx.catalog.get(song_id)
    if song is not None:
        source = ctx.illustration_source(song)
        if source is not None:
            return original.image_data_uri(ctx.paths, source)
    return original.asset_uri(ctx.paths, "html/otherimg/phigros.png")


def _random_sign_background(ctx: CommandContext) -> str:
    # Use the same fully-inlined image path policy as the other original HTML renderers.
    source = random_background_source(ctx.paths)
    if source is not None:
        uri = original.image_data_uri(ctx.paths, source)
        if uri:
            return uri
    return original.asset_uri(ctx.paths, "html/otherimg/phigros.png")


def _challenge_mode(snapshot: SaveSnapshot | None) -> int:
    if snapshot is None:
        return 0
    value = _as_int(snapshot.challenge_mode_rank)
    return max(0, min(5, value // 100))


def _challenge_rank(snapshot: SaveSnapshot | None) -> int:
    if snapshot is None:
        return 0
    return _as_int(snapshot.challenge_mode_rank) % 100


def _avatar(snapshot: SaveSnapshot | None) -> str:
    raw_user = snapshot.raw.get("gameuser") if snapshot and isinstance(snapshot.raw.get("gameuser"), dict) else {}
    return str(raw_user.get("avatar") or "Introduction")


def _percent_text(value: int | float, total: int | float) -> str:
    try:
        percentage = float(value) / float(total) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        percentage = 0.0
    return f"{max(0, min(100, round(percentage)))}%"


def _signed_notes(value: int) -> str:
    return f"{value:+d}"


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_transfer_args(args: str) -> tuple[str, int] | None:
    cleaned = re.sub(r"\[CQ:at,qq=(\d+)[^\]]*\]", r"\1", args or "")
    cleaned = cleaned.replace("<", " ").replace(">", " ").replace("@", " ")
    parts = [part for part in re.split(r"\s+", cleaned.strip()) if part]
    if len(parts) < 2:
        return None
    first_number = next((part for part in parts if re.fullmatch(r"\d+", part)), "")
    last_number = next((part for part in reversed(parts) if re.fullmatch(r"\d+", part)), "")
    if not first_number or not last_number:
        return None
    target = first_number
    amount = _as_int(last_number)
    if target == last_number and len(parts) >= 2:
        target = parts[0]
        amount = _as_int(parts[1])
    return str(target), amount
