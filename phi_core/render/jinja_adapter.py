from __future__ import annotations

import copy
import json
import random
from datetime import datetime
from collections.abc import MutableMapping
from typing import Any

from ..data.loader import SongCatalog
from ..data.illustrations import (
    background_illustration_url,
    find_background_illustration_file,
    is_known_online_illustration_id,
    use_remote_illustrations,
)
from ..data.resources import latest_version_log, load_version_log
from ..models import (
    ALL_LEVELS,
    Best30Result,
    ChartEntry,
    LEVELS,
    LevelScoreSummary,
    PhiSuggestEntry,
    SaveSnapshot,
    ScoreListEntry,
    ScoreRecord,
    Song,
    SuggestEntry,
    UpdateProgressSummary,
    UserSummary,
)
from ..paths import PluginPaths
from ..query import iter_history_score_events, iter_score_records, rks_from_acc
from ..query.progress import money_to_kib
from ..query.progress import extract_modified_datetime, format_datetime
from . import original


def help_data(paths: PluginPaths, *, cmd_head: str = "phi", is_master: bool = False) -> dict[str, Any]:
    help_path = paths.info / "help.json"
    groups = json.loads(help_path.read_text(encoding="utf-8-sig")) if help_path.exists() else []
    if not isinstance(groups, list):
        groups = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        for item in group.get("list") or []:
            if isinstance(item, dict) and item.get("img"):
                item["imgSrc"] = _asset_uri(paths, f"html/otherimg/{item['img']}")
    return {
        "helpGroup": groups,
        "cmdHead": cmd_head,
        "isMaster": is_master,
        "background": original._random_background(paths),
    }


def b30_data(paths: PluginPaths, result: Best30Result, snapshot: SaveSnapshot) -> dict[str, Any]:
    records = result.records
    phi_records = result.phi_records[:3] or [record for record in records if record.acc >= 100][:3]
    background = original._random_background_for_records(paths, [*phi_records, *records])
    return {
        "gameuser": _with_user_assets(paths, original._gameuser(snapshot)),
        "Date": format_datetime(extract_modified_datetime(snapshot.raw)),
        "stats": original._level_stats(records),
        "spInfo": _b30_sp_info(paths, result, snapshot),
        "phi": [_score_record_data(paths, record, f"P{index}", result=result, index=index, phi=True) for index, record in enumerate(phi_records, 1)],
        "b19_list": [
            _score_record_data(paths, record, f"#{index}", result=result, index=index, phi=False)
            for index, record in enumerate(records, 1)
        ],
        "background": background,
        "theme": "default",
    }


def arcgros_b19_data(paths: PluginPaths, result: Best30Result, snapshot: SaveSnapshot) -> dict[str, Any]:
    data = b30_data(paths, result, snapshot)
    gameuser = data.get("gameuser")
    if isinstance(gameuser, dict):
        gameuser["backgroundUrl"] = data.get("background") or original._random_background(paths)
    data["b19_list"] = list(data.get("b19_list") or [])[:19]
    return data


def dss2_record_list_data(
    paths: PluginPaths,
    records: list[ScoreRecord],
    snapshot: SaveSnapshot,
    *,
    sp_info: list[str] | None = None,
    phi_records: list[ScoreRecord] | None = None,
    computed_rks: float | None = None,
) -> dict[str, Any]:
    gameuser = _with_user_assets(paths, original._gameuser(snapshot))
    gameuser["rks"] = computed_rks if computed_rks is not None else original._record_list_rks(records)
    background = original._random_background_for_records(paths, records)
    header_ill = original._record_illustration(paths, records[0]) if records else background
    return {
        "gameuser": gameuser,
        "BSIllPath": header_ill,
        "phi": [_dss2_record_data(paths, record) for record in (phi_records or [])],
        "b19_list": [_dss2_record_data(paths, record) for record in records],
        "spInfo": sp_info or [],
        "theme": "default",
        "background": background,
    }


def list_data(paths: PluginPaths, entries: list[ScoreListEntry], *, title: str = "Score List", limit: int = 80) -> dict[str, Any]:
    visible = entries[:limit]
    return {
        "head_title": title,
        "song": [_score_list_entry_data(paths, entry) for entry in visible],
        "theme": "default",
        "background": original._random_background_for_entries(paths, visible),
    }


def suggest_data(
    paths: PluginPaths,
    entries: list[SuggestEntry],
    *,
    phi_entries: list[PhiSuggestEntry] | None = None,
    title: str = "推分建议",
) -> dict[str, Any]:
    groups: dict[int, list[dict[str, Any]]] = {index: [] for index in range(6)}
    for entry in entries:
        groups[_suggest_type(entry.target_acc)].append(_suggest_entry_data(paths, entry))
    return {
        "head_title": title,
        "phisong": [_phi_suggest_entry_data(paths, entry) for entry in (phi_entries or [])],
        "song": [groups[index] for index in range(6)],
        "theme": "default",
        "background": original._random_background_for_suggestions(paths, entries),
    }


def table_data(
    paths: PluginPaths,
    charts: list[ChartEntry],
    *,
    difficulty: float,
    version_label: str = "current",
    record_map: dict[tuple[str, str], ScoreRecord] | None = None,
    snapshot: SaveSnapshot | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[ChartEntry]] = {}
    for chart in sorted(charts, key=lambda item: (item.difficulty, item.rank, item.song_title)):
        grouped.setdefault(f"{chart.difficulty:.1f}", []).append(chart)
    gameuser = _with_user_assets(paths, original._gameuser(snapshot)) if snapshot is not None else None
    if gameuser is not None:
        gameuser["date"] = format_datetime(extract_modified_datetime(snapshot.raw))
    records = record_map or {}
    return {
        "_imgPath": "html/otherimg/",
        "title": {
            "version": version_label,
            "total": len(charts),
            "difficulty": f"{difficulty:g}",
        },
        "gameuser": gameuser,
        "spInfo": [],
        "table": [
            {
                "difficulty": label,
                "rating": original._table_bucket_rating(bucket, records),
                "ratingImg": _rating_img(paths, original._table_bucket_rating(bucket, records)),
                "songs": [_table_song_data(paths, chart, records.get((chart.song_id, chart.rank)), show_score=gameuser is not None) for chart in bucket],
            }
            for label, bucket in grouped.items()
        ],
        "theme": "default",
        "background": original._random_background_for_charts(paths, charts),
    }


def chap_data(paths: PluginPaths, summary: Any, *, snapshot: SaveSnapshot, catalog: SongCatalog) -> dict[str, Any]:
    chapter_name = str(getattr(summary, "name", "") or "UNKNOWN")
    record_map = {
        (record.song_id, record.rank): record
        for record in iter_score_records(snapshot, catalog)
    }
    songs = [
        song
        for song in catalog.all_songs()
        if chapter_name == "AllSong" or song.chapter == chapter_name
    ]
    song_box: list[dict[str, Any]] = []
    rank_total = {rank: 0 for rank in LEVELS}
    rank_acc = {rank: 0.0 for rank in LEVELS}
    for song in songs:
        chart_data: dict[str, dict[str, Any]] = {}
        for chart in song.display_charts():
            if chart.rank not in LEVELS or chart.difficulty is None:
                continue
            record = record_map.get((song.id, chart.rank))
            chart_data[chart.rank] = _chap_chart_data(paths, chart.difficulty, record)
            rank_total[chart.rank] += 1
            if record is not None:
                rank_acc[chart.rank] += record.acc
        if chart_data:
            song_box.append({
                "illustration": original._song_illustration(paths, song),
                "chart": chart_data,
            })
    top_records = list(getattr(summary, "top_records", []) or [])
    return {
        "_imgPath": "html/otherimg",
        "chapIll": _chap_illustration(paths, chapter_name, top_records),
        "player": {"id": original._gameuser(snapshot)["PlayerId"]},
        "chapName": chapter_name,
        "count": _chap_count(summary),
        "song_box": song_box,
        "progress": {
            rank: _average_acc_progress(rank_acc[rank], rank_total[rank])
            for rank in LEVELS
            if rank_total[rank]
        },
        "num": rank_total.get("EZ") or len(song_box),
        "theme": "default",
        "background": original._random_background_for_records(paths, top_records),
    }


def history_b30_data(paths: PluginPaths, changes: list[Any], snapshot: SaveSnapshot | None = None) -> dict[str, Any]:
    gameuser = _with_user_assets(paths, original._gameuser(snapshot)) if snapshot is not None else {
        "avatar": "Introduction",
        "avatarImg": _avatar_img(paths, "Introduction"),
        "PlayerId": "UNKNOWN",
        "rks": 0.0,
        "ChallengeMode": 0,
        "ChallengeModeRank": 0,
        "challengeImg": _challenge_img(paths, 0),
        "data": "0KiB",
    }
    records = _history_b30_records(changes)
    return {
        "gameuser": gameuser,
        "Date": format_datetime(extract_modified_datetime(snapshot.raw)) if snapshot is not None else format_datetime(datetime.now()),
        "spInfo": "History B30",
        "rows": [_history_b30_row(paths, change, index) for index, change in enumerate(changes)],
        "theme": "default",
        "background": original._random_background_for_records(paths, records),
    }


def analyze_save_history_data(
    paths: PluginPaths,
    summary: Any,
    *,
    history: dict[str, Any] | None = None,
    catalog: SongCatalog | None = None,
) -> dict[str, Any]:
    """Build the upstream `analyzeSaveHistory` stats object from Python history data."""
    return {
        "stats": {
            "generatedAt": format_datetime(datetime.now()),
            "totalDays": _as_int(getattr(summary, "total_days", 0)),
            "totalUpdates": _as_int(getattr(summary, "total_updates", 0)),
            "mostPlayedSongsTop3": _length_list(_pair_rows(getattr(summary, "most_played", []), key_name="id")),
            "rksMaxUpDay": _delta_day(getattr(summary, "rks_max_up", None), digits=4),
            "rksMaxDownDay": _delta_day(getattr(summary, "rks_max_down", None), digits=4),
            "mostNewRecordsDaysTop3": _length_list(_pair_rows(getattr(summary, "most_new_records", []), key_name="day")),
            "dataMaxUpDownDay": {
                "up": _data_delta_day(getattr(summary, "data_max_up", None)),
                "down": _data_delta_day(getattr(summary, "data_max_down", None)),
            },
            "latestPushScoreDaysTop3": _length_list(_time_rows(getattr(summary, "latest_push_times", []))),
            "mostApDaysTop3": _length_list(_pair_rows(getattr(summary, "most_ap_days", []), key_name="day")),
            "resTotalScoreRecords": _history_note_totals(paths, history or {}, catalog),
        },
        "theme": "default",
        "background": original._random_background(paths),
    }


def atlas_data(paths: PluginPaths, song: Song, *, comments: dict[str, Any] | None = None) -> dict[str, Any]:
    illustration = original._song_illustration(paths, song)
    notes = _load_notes_info(paths)
    return {
        "song": song.title,
        "composer": song.composer,
        "length": song.length,
        "spinfo": song.sp_info,
        "chart": [_atlas_chart_data(notes, song, chart) for chart in song.display_charts()],
        "illustration": illustration,
        "isOriginal": bool(song.is_original),
        "bpm": song.bpm,
        "illustrator": song.illustrator,
        "chapter": song.chapter,
        "comment": _atlas_comment_data(comments),
        "theme": "default",
        "background": illustration,
    }


def chart_info_data(
    paths: PluginPaths,
    song: Song,
    rank: str,
    *,
    tags: dict[str, Any] | None = None,
    user_tags: list[str] | None = None,
    chart_img: str = "",
) -> dict[str, Any]:
    chart = song.charts.get(rank)
    if chart is None:
        return {}
    illustration = original._song_illustration(paths, song)
    note_info = _chart_note_info(paths, song.id, rank, chart.combo)
    words = _chart_words(tags or {}, user_tags or [])
    words_max = max([item["value"] for item in words], default=1)
    return {
        "song": song.title,
        "length": song.length or "-",
        "rank": rank,
        "difficulty": _chart_difficulty_text(chart),
        "charter": str(getattr(chart, "charter", "") or "-"),
        "illustration": illustration,
        "tap": note_info["tap"],
        "drag": note_info["drag"],
        "hold": note_info["hold"],
        "flick": note_info["flick"],
        "combo": note_info["combo"],
        "distribution": note_info["distribution"],
        "chartLength": note_info["chart_length"],
        "words": words,
        "wordsMaxValue": max(1, int(words_max * 1.2)),
        "tip": "API" if words else "No data",
        "chartImg": chart_img,
        "theme": "default",
        "background": illustration,
    }


def rand_data(paths: PluginPaths, song: Song, chart: ChartEntry) -> dict[str, Any]:
    song_chart = song.charts.get(chart.rank)
    illustration = original._song_illustration(paths, song)
    return {
        "illustration": illustration,
        "song": song.title,
        "composer": song.composer,
        "charter": str(getattr(song_chart, "charter", "") or ""),
        "illustrator": song.illustrator,
        "difficulty": _chart_entry_difficulty_text(chart, song_chart),
        "rank": chart.rank,
        "theme": "default",
        "background": illustration,
    }


def clg_data(paths: PluginPaths, target: int, charts: list[ChartEntry]) -> dict[str, Any]:
    return {
        "tot_clg": int(target),
        "songs": [_clg_song_data(paths, chart) for chart in charts],
        "theme": "default",
        "background": original._random_background_for_charts(paths, charts),
    }


def user_setting_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["theme"] = prepared.get("theme") or "default"
    prepared["background"] = prepared.get("background") or original._random_background(paths)
    return prepared


def ill_data(paths: PluginPaths, illustration: Any, illustrator: str = "") -> dict[str, Any]:
    image = original.image_data_uri(paths, illustration)
    return {
        "illustration": image,
        "illustrator": illustrator or "Unknown",
        "theme": "default",
        "background": image,
    }


def jrrp_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["bkg"] = original.image_data_uri(paths, prepared.get("bkg")) or original._random_background(paths)
    prepared["theme"] = prepared.get("theme") or "default"
    prepared["background"] = ""
    prepared["bodyClass"] = f"{prepared.get('bodyClass', '')} no-layout-background".strip()
    return prepared


def sign_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["avatar"] = original._avatar_name(paths, str(prepared.get("avatar") or "Introduction"))
    prepared["avatarImg"] = _avatar_img(paths, prepared["avatar"])
    prepared["challengeImg"] = _challenge_img(paths, prepared.get("ChallengeMode"))
    prepared["background"] = original.image_data_uri(paths, prepared.get("background")) or original._random_background(paths)
    for task in prepared.get("dailyTasks") or []:
        if isinstance(task, dict):
            task["illustration"] = original.image_data_uri(paths, task.get("illustration")) or original.asset_uri(paths, "html/otherimg/phigros.png")
    prepared["theme"] = prepared.get("theme") or "default"
    return prepared


def guess_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["illustration"] = original.image_data_uri(paths, prepared.get("illustration"))
    prepared["ans"] = original.image_data_uri(paths, prepared.get("ans")) if prepared.get("ans") else ""
    prepared["theme"] = prepared.get("theme") or "default"
    prepared["background"] = ""
    return prepared


def newlog_data(
    paths: PluginPaths,
    log: Any,
    *,
    catalog: SongCatalog | None = None,
    update_logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ans": original._newlog_rows(paths, log, catalog=catalog, update_logs=update_logs or []),
        "theme": "default",
        "background": original._random_background(paths),
    }


def ranking_list_data(paths: PluginPaths, data: dict[str, Any], catalog: SongCatalog | None = None) -> dict[str, Any]:
    users = data.get("users") if isinstance(data.get("users"), list) else []
    me = data.get("me") if isinstance(data.get("me"), dict) else {}
    me_line = _with_user_assets(paths, original._ranking_large_line(paths, me, catalog))
    user_lines = [
        _with_user_assets(paths, original._ranking_small_line(paths, item if isinstance(item, dict) else {}, fallback_index=index + 1, catalog=catalog))
        for index, item in enumerate(users[:5])
    ]
    while len(user_lines) < 5:
        user_lines.append({"playerId": "NO INFO", "index": len(user_lines) + 1})
    background = str(me_line.get("backgroundurl") or original._random_background(paths))
    me_line["backgroundurl"] = background
    me_line["b30list"] = _ranking_template_b30_groups(paths, me_line.get("b30list"))
    return {
        "users": user_lines,
        "me": me_line,
        "theme": "default",
        "background": background,
    }


def ranking_list_old_data(paths: PluginPaths, data: dict[str, Any], catalog: SongCatalog | None = None) -> dict[str, Any]:
    users = data.get("users") if isinstance(data.get("users"), list) else []
    me = data.get("me") if isinstance(data.get("me"), dict) else {}
    rows = [
        _ranking_old_user_line(paths, item if isinstance(item, dict) else {}, fallback_index=index + 1, catalog=catalog)
        for index, item in enumerate(users[:5])
    ]
    while len(rows) < 5:
        rows.append(_ranking_old_empty_line(len(rows) + 1))
    return {
        "Title": str(data.get("Title") or "RankingScore排行榜"),
        "totDataNum": data.get("totDataNum") or data.get("totNum") or 0,
        "BotNick": str(data.get("BotNick") or "AstrBot"),
        "users": rows[:6],
        "theme": "default",
        "background": original._random_background(paths),
    }


def score_data(
    paths: PluginPaths,
    song: Song,
    records: list[ScoreRecord],
    snapshot: SaveSnapshot,
    *,
    b30_result: Best30Result | None = None,
    history: list[Any] | None = None,
    ranklist: dict[str, Any] | None = None,
    selected_rank: str | None = None,
    ap_fc_count: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gameuser = original._gameuser(snapshot)
    phi_rank = {
        (record.song_id, record.rank): index
        for index, record in enumerate((b30_result.phi_records if b30_result else [])[:3], 1)
    }
    best_rank = {
        (record.song_id, record.rank): index
        for index, record in enumerate((b30_result.records if b30_result else [])[:27], 1)
    }
    record_map = {record.rank: record for record in records}
    score_rows: list[dict[str, Any]] = []
    for rank in LEVELS:
        chart = song.charts.get(rank)
        if chart is None:
            continue
        record = record_map.get(rank)
        score_rows.append(_score_template_rank_data(
            rank,
            chart.difficulty or 0.0,
            record,
            phi_rank.get((song.id, rank)),
            best_rank.get((song.id, rank)),
            ap_fc_count,
        ))
    illustration = original._song_illustration(paths, song)
    return {
        "songName": song.title,
        "PlayerId": gameuser["PlayerId"],
        "avatar": gameuser["avatar"],
        "avatarImg": _avatar_img(paths, gameuser["avatar"]),
        "Rks": f"{float(gameuser['rks'] or 0):.4f}",
        "Date": format_datetime(extract_modified_datetime(snapshot.raw)),
        "ChallengeMode": gameuser["ChallengeMode"],
        "ChallengeModeRank": gameuser["ChallengeModeRank"],
        "challengeImg": _challenge_img(paths, gameuser["ChallengeMode"]),
        "CLGMOD": "",
        "EX": False,
        "scoreData": _score_data_with_assets(paths, score_rows),
        "history": [_score_history_data(item) for item in (history or records)[:16]],
        "illustration": illustration,
        "background": illustration,
        "ranklist": _score_ranklist_data(ranklist, selected_rank) if ranklist else None,
        "theme": "default",
    }


def update_data(
    paths: PluginPaths,
    summary: UpdateProgressSummary,
    *,
    history: dict[str, Any] | None = None,
    task_data: list[dict[str, Any] | None] | None = None,
    task_time: str = "",
    notes: int | None = None,
    theme: str = "default",
) -> dict[str, Any]:
    challenge = _as_int(summary.challenge_mode_rank)
    rks_history, rks_range, rks_date = _series_lines(
        history or {},
        "rks",
        current=(summary.modified_at, summary.ranking_score),
        money=False,
    )
    data_money = _format_money(summary.data_money)
    return {
        "PlayerId": summary.player_id or summary.player_name or "UNKNOWN",
        "Rks": f"{summary.ranking_score:.4f}",
        "ChallengeMode": max(0, min(5, challenge // 100)),
        "ChallengeModeRank": challenge % 100,
        "challengeImg": _challenge_img(paths, max(0, min(5, challenge // 100))),
        "Notes": data_money if notes is None else f"{notes} Notes",
        "Date": summary.modified_at,
        "added_rks_notes": [
            _signed_delta(summary.rks_delta, digits=4),
            _signed_delta(summary.data_delta, suffix="KiB"),
        ],
        "rks_history": rks_history,
        "rks_range": rks_range,
        "rks_date": rks_date,
        "box_line": _update_box_lines(paths, summary.recent_days),
        "task_data": task_data or _first_record_task(paths, summary),
        "task_time": task_time,
        "tips": "",
        "theme": theme or "default",
        "background": original._random_background(paths),
    }


def userinfo_data(
    paths: PluginPaths,
    summary: UserSummary,
    *,
    snapshot: SaveSnapshot,
    history: dict[str, Any] | None = None,
    catalog: SongCatalog | None = None,
    background: str | Any | None = None,
) -> dict[str, Any]:
    gameuser = original._gameuser(snapshot)
    requested_background = original._source_data_uri(paths, background) if background is not None else ""
    if not requested_background:
        requested_background = original._random_background(paths)
    rks_history, rks_range, rks_date = _series_lines(history or {}, "rks", money=False)
    data_history, data_range, data_date = _series_lines(history or {}, "data", money=True)
    acc_rks_data, acc_rks_range, acc_rks_range_labels = _info_acc_rks(snapshot, catalog)
    return {
        "gameuser": _with_user_assets(paths, {
            **gameuser,
            "backgroundurl": _info_background(paths, snapshot),
            "selfIntro": _info_intro(snapshot, summary),
            "CLGMOD": "",
            "EX": False,
        }),
        "userstats": _info_userstats_list(_info_stats(snapshot, catalog)),
        "rks_history": rks_history,
        "data_history": data_history,
        "rks_range": rks_range,
        "data_range": [f"{value:.0f}KiB" for value in data_range],
        "rks_date": rks_date,
        "data_date": data_date,
        "acc_rks_data": acc_rks_data,
        "acc_rks_range": acc_rks_range,
        "acc_rks_AccRange": acc_rks_range_labels,
        "background": requested_background,
        "theme": "default",
    }


def lvscore_data(paths: PluginPaths, summary: LevelScoreSummary, snapshot: SaveSnapshot) -> dict[str, Any]:
    gameuser = original._gameuser(snapshot)
    rating = _dominant_rating(summary.rating_counts)
    range_bottom, range_top = _range_bounds(summary.range_text, summary.lowest_difficulty, summary.highest_difficulty)
    return {
        "illustration": original._random_background(paths),
        "avatar": gameuser["avatar"],
        "avatarImg": _avatar_img(paths, gameuser["avatar"]),
        "PlayerId": gameuser["PlayerId"],
        "rks": float(gameuser["rks"] or 0),
        "ChallengeMode": gameuser["ChallengeMode"],
        "ChallengeModeRank": gameuser["ChallengeModeRank"],
        "challengeImg": _challenge_img(paths, gameuser["ChallengeMode"]),
        "range": {
            "bottom": range_bottom,
            "top": range_top,
            "left": 0,
            "length": 100,
        },
        "tot": {
            "songs": summary.total_charts,
            "charts": summary.total_charts,
            "score": _std_score(summary.total_charts * 1_000_000),
            "at": summary.rank_counts.get("AT", 0),
            "in": summary.rank_counts.get("IN", 0),
            "hd": summary.rank_counts.get("HD", 0),
            "ez": summary.rank_counts.get("EZ", 0),
        },
        "real": {
            "songs": summary.played_charts,
            "charts": summary.played_charts,
            "score": _std_score(summary.avg_score),
            "at": summary.rank_counts.get("AT", 0),
            "in": summary.rank_counts.get("IN", 0),
            "hd": summary.rank_counts.get("HD", 0),
            "ez": summary.rank_counts.get("EZ", 0),
        },
        "rating": {**summary.rating_counts, "tot": rating},
        "ratingTotImg": _rating_img(paths, rating),
        "ratingImgs": _rating_img_map(paths),
        "progress_phi": _percentage(summary.phi_count, summary.total_charts),
        "progress_fc": _percentage(summary.fc_count, summary.total_charts),
        "date": format_datetime(extract_modified_datetime(snapshot.raw)),
        "highest": summary.highest_difficulty,
        "lowest": summary.lowest_difficulty,
        "tot_acc": summary.avg_acc,
        "tot_cleared": summary.played_charts,
        "tot_fc": summary.fc_count,
        "tot_phi": summary.phi_count,
        "background": original._random_background(paths),
    }


def newnotice_data(paths: PluginPaths, notice: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(notice)
    data["background"] = original._random_background(paths)
    data["_data"] = copy.deepcopy(notice)
    return data


def _asset_uri(paths: PluginPaths, relative: str) -> str:
    return original.asset_uri(paths, relative)


def _rating_img(paths: PluginPaths, rating: Any) -> str:
    return _asset_uri(paths, f"html/otherimg/{_rating_asset(str(rating or 'NEW'))}.png")


def _avatar_img(paths: PluginPaths, avatar: Any) -> str:
    name = original._avatar_name(paths, str(avatar or "Introduction"))
    return _asset_uri(paths, f"html/avatar/{name}.png") or _asset_uri(paths, "html/avatar/Introduction.png")


def _challenge_img(paths: PluginPaths, challenge_mode: Any) -> str:
    return _asset_uri(paths, f"html/otherimg/{max(0, min(5, _as_int(challenge_mode)))}.png")


def _rating_img_map(paths: PluginPaths) -> dict[str, str]:
    names = ("phi", "FC", "V", "S", "A", "B", "C", "F", "NEW", "EZ", "HD", "IN", "AT", "0", "1", "2", "3", "4", "5")
    return {name: _asset_uri(paths, f"html/otherimg/{name}.png") for name in names}


def _with_user_assets(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["avatarImg"] = _avatar_img(paths, prepared.get("avatar"))
    prepared["challengeImg"] = _challenge_img(paths, prepared.get("ChallengeMode"))
    return prepared


def _apply_template_assets(paths: PluginPaths, value: Any) -> None:
    if isinstance(value, MutableMapping):
        if "avatar" in value:
            value.setdefault("avatarImg", _avatar_img(paths, value.get("avatar")))
        if "ChallengeMode" in value:
            value.setdefault("challengeImg", _challenge_img(paths, value.get("ChallengeMode")))
        if "challenge" in value:
            value.setdefault("challengeImg", _challenge_img(paths, _as_int(value.get("challenge")) // 100))
        if "Rating" in value:
            value.setdefault("ratingImg", _rating_img(paths, value.get("Rating")))
        rating = value.get("rating")
        if rating is not None and not isinstance(rating, (dict, list, tuple)):
            value.setdefault("ratingImg", _rating_img(paths, rating))
        if "img" in value and "imgSrc" not in value and value.get("img"):
            value["imgSrc"] = _asset_uri(paths, f"html/otherimg/{value['img']}")
        for key, item in list(value.items()):
            if key in {"ratingImgs", "countImgs"}:
                continue
            _apply_template_assets(paths, item)
        if "theme" in value or "background" in value or "helpGroup" in value:
            value.setdefault("dataImg", _asset_uri(paths, "html/otherimg/data.png"))
            value.setdefault("phiImg", _rating_img(paths, "phi"))
            value.setdefault("newImg", _rating_img(paths, "NEW"))
            value.setdefault("challenge5Img", _challenge_img(paths, 5))
            value.setdefault("titleImg", _asset_uri(paths, "html/otherimg/title.png"))
            value.setdefault("shineAfterImg", _asset_uri(paths, "html/jrrp/ShineAfter.removebg.png"))
            value.setdefault("phigrosIconImg", _asset_uri(paths, "html/otherimg/Phigros_Icon_3.0.0.png"))
            value.setdefault("ratingImgs", _rating_img_map(paths))
            value.setdefault("countImgs", value.get("ratingImgs"))
    elif isinstance(value, list):
        for item in value:
            _apply_template_assets(paths, item)


def prepare_dss2_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["phi"] = prepared.get("phi") or []
    prepared["b19_list"] = prepared.get("b19_list") or []
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_suggest_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    groups = prepared.get("song")
    if not isinstance(groups, list):
        groups = []
    while len(groups) < 6:
        groups.append([])
    prepared["song"] = groups[:6]
    prepared["phisong"] = prepared.get("phisong") or []
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_arcgros_b19_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    for group_name in ("phi", "b19_list"):
        for song in prepared.get(group_name) or []:
            if isinstance(song, dict):
                song.setdefault("std_score", _std_score(song.get("score")))
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_lvsco_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    rating = prepared.get("rating")
    if isinstance(rating, dict):
        values = [int(float(value)) for key, value in rating.items() if key != "tot" and _is_number(value)]
        prepared["rating_max"] = max(values) if values else 1
    else:
        prepared["rating_max"] = 1
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_newnotice_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    notices = prepared.get("notices") or prepared.get("info") or prepared.get("list") or []
    if isinstance(notices, dict):
        notices = [notices]
    if not isinstance(notices, list):
        notices = []
    for notice in notices:
        if isinstance(notice, dict):
            notice.setdefault("date_text", _notice_date_text(notice.get("date")))
    prepared["notices"] = notices
    return prepared


def prepare_score_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    score_data = prepared.get("scoreData")
    if isinstance(score_data, _ScoreData):
        prepared["scoreData"] = score_data
    elif isinstance(score_data, dict):
        prepared["scoreData"] = _ScoreData([value for value in score_data.values() if isinstance(value, dict)])
    elif isinstance(score_data, list):
        prepared["scoreData"] = _ScoreData([value for value in score_data if isinstance(value, dict)])
    else:
        prepared["scoreData"] = _ScoreData([])
    by_rank = {str(row.get("rank") or ""): row for row in prepared["scoreData"] if isinstance(row, dict)}
    for rank in LEVELS:
        prepared[rank] = by_rank.get(rank)
    prepared["CLGMOD"] = prepared.get("CLGMOD") or ""
    prepared["EX"] = bool(prepared.get("EX"))
    prepared["history"] = prepared.get("history") or []
    if not prepared.get("background"):
        prepared["background"] = prepared.get("illustration")
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_update_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["added_rks_notes"] = _ensure_length(prepared.get("added_rks_notes"), 2, "")
    prepared["rks_history"] = prepared.get("rks_history") or []
    prepared["rks_range"] = _ensure_length(prepared.get("rks_range"), 2, 0.0)
    prepared["rks_date"] = _ensure_length(prepared.get("rks_date"), 2, "")
    prepared["box_line"] = prepared.get("box_line") or []
    prepared["task_data"] = prepared.get("task_data") or []
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_userinfo_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["gameuser"] = prepared.get("gameuser") or {}
    prepared["userstats"] = prepared.get("userstats") or []
    prepared["rks_history"] = prepared.get("rks_history") or []
    prepared["data_history"] = prepared.get("data_history") or []
    prepared["rks_range"] = _ensure_length(prepared.get("rks_range"), 2, 0.0)
    prepared["data_range"] = _ensure_length(prepared.get("data_range"), 2, "")
    prepared["rks_date"] = _ensure_length(prepared.get("rks_date"), 2, "")
    prepared["data_date"] = _ensure_length(prepared.get("data_date"), 2, "")
    prepared["acc_rks_data"] = prepared.get("acc_rks_data") or []
    prepared["acc_rks_range"] = _ensure_length(prepared.get("acc_rks_range"), 2, 0.0)
    prepared["acc_rks_AccRange"] = prepared.get("acc_rks_AccRange") or []
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_chap_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["count"] = prepared.get("count") or {"tot": 0}
    prepared["song_box"] = prepared.get("song_box") or []
    prepared["progress"] = prepared.get("progress") or {}
    prepared["num"] = _as_int(prepared.get("num")) or len(prepared["song_box"])
    if not prepared.get("chapIll"):
        prepared["chapIll"] = prepared.get("background") or ""
    prepared["countImgs"] = _rating_img_map(paths)
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_history_b30_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    gameuser = prepared.get("gameuser")
    prepared["gameuser"] = gameuser if isinstance(gameuser, dict) else {}
    prepared["rows"] = prepared.get("rows") or []
    prepared["spInfo"] = prepared.get("spInfo") or ""
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_analyze_save_history_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    stats = prepared.get("stats")
    if not isinstance(stats, dict):
        stats = {}
    for key in ("mostPlayedSongsTop3", "mostNewRecordsDaysTop3", "latestPushScoreDaysTop3", "mostApDaysTop3"):
        stats[key] = _length_list(stats.get(key) if isinstance(stats.get(key), list) else [])
    stats.setdefault("rksMaxUpDay", {"day": "--", "delta": "--"})
    stats.setdefault("rksMaxDownDay", {"day": "--", "delta": "--"})
    stats.setdefault("dataMaxUpDownDay", {"up": {"day": "--", "deltaBytes": "0B"}, "down": {"day": "--", "deltaBytes": "0B"}})
    stats.setdefault("resTotalScoreRecords", _empty_note_totals())
    prepared["stats"] = stats
    return prepared


def prepare_atlas_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["chart"] = prepared.get("chart") or []
    comment = prepared.get("comment")
    if isinstance(comment, dict):
        comment["list"] = comment.get("list") or []
        prepared["comment"] = comment
    else:
        prepared["comment"] = None
    if not prepared.get("background"):
        prepared["background"] = prepared.get("illustration") or ""
    return prepared


def prepare_chart_info_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["distribution"] = _normalize_distribution(prepared.get("distribution"))
    words = prepared.get("words")
    prepared["words"] = words if isinstance(words, list) else []
    prepared["wordsMaxValue"] = max(1, _as_int(prepared.get("wordsMaxValue")))
    prepared["tip"] = prepared.get("tip") or ("API" if prepared["words"] else "No data")
    if not prepared.get("background"):
        prepared["background"] = prepared.get("illustration") or ""
    return prepared


def prepare_rand_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    if not prepared.get("background"):
        prepared["background"] = prepared.get("illustration") or ""
    return prepared


def prepare_clg_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    songs = prepared.get("songs")
    prepared["songs"] = songs if isinstance(songs, list) else []
    prepared["tot_clg"] = _as_int(prepared.get("tot_clg"))
    return prepared


def prepare_user_setting_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["pageTitle"] = prepared.get("pageTitle") or "Phi-Plugin 用户设置"
    prepared["pageDescription"] = prepared.get("pageDescription") or ""
    items = prepared.get("items")
    prepared["items"] = items if isinstance(items, list) else []
    for item in prepared["items"]:
        if isinstance(item, dict):
            options = item.get("options")
            item["options"] = options if isinstance(options, list) else []
    return prepared


def prepare_ill_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["illustration"] = prepared.get("illustration") or prepared.get("background") or ""
    prepared["illustrator"] = prepared.get("illustrator") or "Unknown"
    if not prepared.get("background"):
        prepared["background"] = prepared["illustration"]
    return prepared


def prepare_jrrp_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["lucky"] = _as_int(prepared.get("lucky"))
    prepared["luckRank"] = _as_int(prepared.get("luckRank"))
    prepared["year"] = prepared.get("year") or ""
    prepared["month"] = prepared.get("month") or ""
    prepared["day"] = prepared.get("day") or ""
    sentence = prepared.get("sentence")
    prepared["sentence"] = sentence if isinstance(sentence, dict) else {"hitokoto": "", "from": ""}
    prepared["good"] = [str(item) for item in (prepared.get("good") if isinstance(prepared.get("good"), list) else [])[:4]]
    prepared["bad"] = [str(item) for item in (prepared.get("bad") if isinstance(prepared.get("bad"), list) else [])[:4]]
    return prepared


def prepare_sign_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["avatar"] = prepared.get("avatar") or "Introduction"
    prepared["PlayerId"] = prepared.get("PlayerId") or "UNKNOWN"
    prepared["Rks"] = prepared.get("Rks") or "0.0000"
    prepared["Date"] = prepared.get("Date") or ""
    prepared["Notes"] = _as_int(prepared.get("Notes"))
    prepared["signDays"] = _as_int(prepared.get("signDays"))
    prepared["ChallengeMode"] = _as_int(prepared.get("ChallengeMode"))
    prepared["ChallengeModeRank"] = _as_int(prepared.get("ChallengeModeRank"))
    prepared["lucky"] = _as_int(prepared.get("lucky"))
    prepared["good"] = [str(item) for item in (prepared.get("good") if isinstance(prepared.get("good"), list) else [])[:4]]
    prepared["bad"] = [str(item) for item in (prepared.get("bad") if isinstance(prepared.get("bad"), list) else [])[:4]]
    prepared["quote"] = prepared.get("quote") or ""
    prepared["edgeRate"] = _sign_edge_rate(prepared.get("edgeRate"))
    tasks = prepared.get("dailyTasks")
    prepared["dailyTasks"] = [task for task in tasks if isinstance(task, dict)] if isinstance(tasks, list) else []
    notice = prepared.get("notice")
    if isinstance(notice, dict):
        content = notice.get("content")
        notice["content"] = [str(item) for item in content] if isinstance(content, list) else []
        prepared["notice"] = notice
    else:
        prepared["notice"] = None
    prepared["calendar"] = _sign_calendar(prepared.get("calendar"))
    return prepared


def prepare_newlog_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    rows = prepared.get("ans")
    normalized_rows: list[list[dict[str, Any]]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, list):
                continue
            normalized_row: list[dict[str, Any]] = []
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                normalized_row.append({
                    "cnt": str(cell.get("cnt") or ""),
                    "col": _as_int(cell.get("col")) or 1,
                    "row": _as_int(cell.get("row")) if "row" in cell else 1,
                    "bkg": str(cell.get("bkg") or "#ffffff00"),
                    "color": str(cell.get("color") or "#000"),
                })
            normalized_rows.append(normalized_row)
    prepared["ans"] = normalized_rows
    return prepared


def prepare_guess_data(data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    prepared["width"] = max(1, _as_int(prepared.get("width")) or 120)
    prepared["height"] = max(1, _as_int(prepared.get("height")) or 120)
    prepared["x"] = max(0, _as_int(prepared.get("x")))
    prepared["y"] = max(0, _as_int(prepared.get("y")))
    prepared["style"] = 1 if _as_int(prepared.get("style")) else 0
    prepared["filterStyle"] = str(prepared.get("filterStyle") or "")
    prepared["illustration"] = str(prepared.get("illustration") or "")
    prepared["ans"] = str(prepared.get("ans") or "")
    prepared["_viewport_width"] = 2048 if prepared["style"] else prepared["width"]
    prepared["_viewport_height"] = 1080 if prepared["style"] else prepared["height"]
    return prepared


def prepare_ranking_list_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    users = prepared.get("users")
    prepared["users"] = users if isinstance(users, list) else []
    me = prepared.get("me")
    prepared["me"] = me if isinstance(me, dict) else {}
    prepared["me"]["rks_history"] = prepared["me"].get("rks_history") or []
    prepared["me"]["rks_range"] = _ensure_length(prepared["me"].get("rks_range"), 2, 0.0)
    prepared["me"]["rks_date"] = _ensure_length(prepared["me"].get("rks_date"), 2, "")
    prepared["me"]["clg_list"] = prepared["me"].get("clg_list") or []
    prepared["me"]["b30list"] = prepared["me"].get("b30list") or _ranking_empty_template_groups()
    if not prepared["me"].get("backgroundurl"):
        prepared["me"]["backgroundurl"] = prepared.get("background") or ""
    if not prepared.get("background"):
        prepared["background"] = prepared["me"].get("backgroundurl") or ""
    _apply_template_assets(paths, prepared)
    return prepared


def prepare_ranking_list_old_data(paths: PluginPaths, data: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(data)
    users = prepared.get("users")
    prepared["users"] = users if isinstance(users, list) else []
    prepared["Title"] = str(prepared.get("Title") or "RankingScore排行榜")
    prepared["BotNick"] = str(prepared.get("BotNick") or "AstrBot")
    prepared["totDataNum"] = prepared.get("totDataNum") or prepared.get("totNum") or 0
    for fallback_index, user in enumerate(prepared["users"], 1):
        if not isinstance(user, dict):
            continue
        user["index"] = _as_int(user.get("index")) or fallback_index
        user["avatar"] = str(user.get("avatar") or "Introduction")
        user["playerId"] = str(user.get("playerId") or "NO INFO")
        user["rks"] = _as_float(user.get("rks"))
        user["ChallengeMode"] = max(0, min(5, _as_int(user.get("ChallengeMode"))))
        user["ChallengeModeRank"] = _as_int(user.get("ChallengeModeRank"))
        user["backgroundurl"] = str(user.get("backgroundurl") or "")
        user["created"] = str(user.get("created") or "")
        user["updated"] = str(user.get("updated") or "")
        user["selfIntro"] = str(user.get("selfIntro") or "")
        b19 = user.get("b19")
        user["b19"] = b19 if isinstance(b19, list) else []
    _apply_template_assets(paths, prepared)
    return prepared


def adapt_template_data(paths: PluginPaths, template_path: str, data: dict[str, Any]) -> dict[str, Any]:
    normalized = template_path.replace("\\", "/").removesuffix(".html")
    prepared: dict[str, Any]
    if normalized == "rand/rand":
        prepared = prepare_rand_data(data)
    elif normalized == "clg/clg":
        prepared = prepare_clg_data(data)
    elif normalized == "setting/userSetting":
        prepared = prepare_user_setting_data(data)
    elif normalized == "ill/ill":
        prepared = prepare_ill_data(data)
    elif normalized == "jrrp/jrrp":
        prepared = prepare_jrrp_data(data)
    elif normalized == "sign/sign":
        prepared = prepare_sign_data(data)
    elif normalized == "guess/guess":
        prepared = prepare_guess_data(data)
    elif normalized == "newSong/newSong":
        prepared = prepare_newlog_data(data)
    elif normalized == "rankingList-old/rankingList":
        prepared = prepare_ranking_list_old_data(paths, data)
    elif normalized == "rankingList/rankingList":
        prepared = prepare_ranking_list_data(paths, data)
    elif normalized in {"chartInfo/chartInfo", "chartImg/chartImg"}:
        prepared = prepare_chart_info_data(data)
    elif normalized == "atlas/atlas":
        prepared = prepare_atlas_data(data)
    elif normalized == "analyzeSaveHistory/analyzeSaveHistory":
        prepared = prepare_analyze_save_history_data(data)
    elif normalized == "historyB30/historyB30":
        prepared = prepare_history_b30_data(paths, data)
    elif normalized == "chap/chap":
        prepared = prepare_chap_data(paths, data)
    elif normalized in {"score/score", "score/scoreOld", "score/scoreRankList"}:
        prepared = prepare_score_data(paths, data)
    elif normalized == "update/update":
        prepared = prepare_update_data(paths, data)
    elif normalized in {"userinfo/userinfo", "userinfo/userinfo-old"}:
        prepared = prepare_userinfo_data(paths, data)
    elif normalized == "arcgrosB19/arcgrosB19":
        prepared = prepare_arcgros_b19_data(paths, data)
    elif normalized == "b19/dss2":
        prepared = prepare_dss2_data(paths, data)
    elif normalized == "suggest/suggest":
        prepared = prepare_suggest_data(paths, data)
    elif normalized == "lvsco/lvsco":
        prepared = prepare_lvsco_data(paths, data)
    elif normalized == "newnotice/newnotice":
        prepared = prepare_newnotice_data(data)
    else:
        prepared = copy.deepcopy(data)
    _apply_template_assets(paths, prepared)
    return prepared


def _score_record_data(
    paths: PluginPaths,
    record: ScoreRecord,
    number: str,
    *,
    result: Best30Result,
    index: int,
    phi: bool,
) -> dict[str, Any]:
    suggest_text, suggest_type = ("无法推分", "")
    if not phi:
        suggest_text, suggest_type = original._record_suggest(result, record, index)
    return {
        "num": number.lstrip("#"),
        "illustration": original._record_illustration(paths, record),
        "rank": record.rank,
        "difficulty": record.difficulty,
        "rks": record.rks,
        "song": record.song_title,
        "Rating": record.rating,
        "ratingImg": _rating_img(paths, record.rating),
        "score": _std_score(record.score),
        "acc": record.acc,
        "suggest": suggest_text,
        "suggestType": suggest_type,
        "accAvg": _acc_avg_value(record, phi=phi),
        "accKind": record.acc_kind or "",
    }


def _dss2_record_data(paths: PluginPaths, record: ScoreRecord) -> dict[str, Any]:
    return {
        "illustration": original._record_illustration(paths, record),
        "rank": record.rank,
        "difficulty": record.difficulty,
        "rks": record.rks,
        "song": record.song_title,
        "Rating": record.rating,
        "ratingImg": _rating_img(paths, record.rating),
        "score": _std_score(record.score),
        "acc": record.acc,
        "suggest": original._record_list_suggest(record),
        "suggestType": original._record_list_suggest_type(record),
    }


def _ranking_template_b30_groups(paths: PluginPaths, groups: Any) -> list[dict[str, Any]]:
    source = groups if isinstance(groups, list) else []
    if not source:
        return _ranking_empty_template_groups()
    result: list[dict[str, Any]] = []
    for fallback, group in zip(("P3", "B3", "F3", "L3"), source):
        if not isinstance(group, dict):
            result.append({"key": fallback, "title": fallback, "list": []})
            continue
        records = group.get("list") if isinstance(group.get("list"), list) else []
        result.append({
            "key": str(group.get("key") or fallback),
            "title": str(group.get("title") or fallback),
            "list": [_ranking_template_b30_card(paths, record) for record in records[:3]],
        })
    while len(result) < 4:
        key = ("P3", "B3", "F3", "L3")[len(result)]
        result.append({"key": key, "title": key, "list": []})
    return result[:4]


def _ranking_old_user_line(
    paths: PluginPaths,
    item: dict[str, Any],
    *,
    fallback_index: int,
    catalog: SongCatalog | None,
) -> dict[str, Any]:
    raw = item.get("save") if isinstance(item.get("save"), dict) else item
    line = original._ranking_large_line(paths, item, catalog)
    if not line.get("playerId") and isinstance(raw, dict):
        line.update(original._ranking_small_line(paths, raw, fallback_index=fallback_index, catalog=catalog))
    line["index"] = _as_int(raw.get("index") if isinstance(raw, dict) else item.get("index")) or fallback_index
    line["me"] = bool(item.get("me") or line.get("me"))
    line["created"] = _ranking_old_created(raw if isinstance(raw, dict) else item)
    line["updated"] = str(line.get("updated") or _ranking_old_updated(raw if isinstance(raw, dict) else item))
    line["b19"] = _ranking_old_b19_from_save(raw if isinstance(raw, dict) else item, catalog) or _ranking_old_b19_rows(line.get("b30list"))
    return line


def _ranking_old_empty_line(index: int) -> dict[str, Any]:
    return {
        "backgroundurl": "",
        "avatar": "Introduction",
        "playerId": "NO INFO",
        "rks": 0.0,
        "ChallengeMode": 0,
        "ChallengeModeRank": 0,
        "index": index,
        "me": False,
        "created": "",
        "updated": "",
        "selfIntro": "",
        "b19": [],
    }


def _ranking_old_b19_from_save(raw: dict[str, Any], catalog: SongCatalog | None) -> list[dict[str, Any]]:
    snapshot = original._snapshot_from_rank_save(raw)
    if snapshot is None or catalog is None:
        return []
    result = original.compute_rank_b30(snapshot, catalog)
    return [_ranking_old_b19_row(record) for record in result.records[:19]]


def _ranking_old_b19_rows(groups: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = groups if isinstance(groups, list) else []
    for group in source:
        if not isinstance(group, dict):
            continue
        records = group.get("list") if isinstance(group.get("list"), list) else []
        for record in records:
            row = _ranking_old_b19_row(record)
            if row is not None:
                rows.append(row)
    while len(rows) < 19:
        rows.append({"acc": 0.0, "difficulty": "", "Rating": "NEW"})
    return rows[:19]


def _ranking_old_b19_row(record: Any) -> dict[str, Any] | None:
    if isinstance(record, ScoreRecord):
        return {
            "acc": record.acc,
            "difficulty": f"{record.rank} {record.difficulty:.1f}",
            "Rating": _rating_asset(record.rating),
        }
    if isinstance(record, dict):
        return {
            "acc": _as_float(record.get("acc")),
            "difficulty": str(record.get("difficulty") or record.get("rank") or ""),
            "Rating": _rating_asset(str(record.get("Rating") or record.get("rating") or "NEW")),
        }
    return None


def _ranking_old_created(raw: dict[str, Any]) -> str:
    save_info = raw.get("saveInfo") if isinstance(raw.get("saveInfo"), dict) else {}
    value = save_info.get("createdAt") or raw.get("createdAt") or raw.get("created")
    if isinstance(value, dict):
        value = value.get("iso") or value.get("date")
    return _date_label(value)


def _ranking_old_updated(raw: dict[str, Any]) -> str:
    save_info = raw.get("saveInfo") if isinstance(raw.get("saveInfo"), dict) else {}
    value = save_info.get("modifiedAt") or save_info.get("updatedAt") or raw.get("updatedAt") or raw.get("updated")
    if isinstance(value, dict):
        value = value.get("iso") or value.get("date")
    return _date_label(value)


def _ranking_empty_template_groups() -> list[dict[str, Any]]:
    return [
        {"key": "P3", "title": "Perfect 3", "list": []},
        {"key": "B3", "title": "Best 3", "list": []},
        {"key": "F3", "title": "Floor 3", "list": []},
        {"key": "L3", "title": "Overflow 3", "list": []},
    ]


def _ranking_template_b30_card(paths: PluginPaths, record: Any) -> dict[str, Any] | None:
    if isinstance(record, ScoreRecord):
        return {
            "illustration": original._record_illustration(paths, record),
            "rank": record.rank,
            "difficulty": record.difficulty,
            "Rating": _rating_asset(record.rating),
        }
    if isinstance(record, dict):
        return {
            "illustration": original._source_data_uri(paths, record.get("illustration")) or str(record.get("illustration") or ""),
            "rank": str(record.get("rank") or ""),
            "difficulty": _as_float(record.get("difficulty")),
            "Rating": _rating_asset(str(record.get("Rating") or record.get("rating") or "NEW")),
        }
    return None


def _clg_song_data(paths: PluginPaths, chart: ChartEntry) -> dict[str, Any]:
    note_info = _chart_note_info(paths, chart.song_id, chart.rank, chart.combo)
    return {
        "illustration": original._chart_illustration(paths, chart),
        "song": chart.song_title,
        "rank": chart.rank,
        "difficulty": chart.difficulty,
        "tap": note_info["tap"],
        "drag": note_info["drag"],
        "hold": note_info["hold"],
        "flick": note_info["flick"],
        "combo": note_info["combo"],
    }


def _sign_edge_rate(value: Any) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    source = value if isinstance(value, dict) else {}
    for rank in ("EZ", "HD", "IN", "AT"):
        raw = source.get(rank) if isinstance(source.get(rank), dict) else {}
        result[rank] = {
            "unlock": str(raw.get("unlock") or "0%"),
            "fc": str(raw.get("fc") or "0%"),
            "phi": str(raw.get("phi") or "0%"),
        }
    return result


def _sign_calendar(value: Any) -> dict[str, Any]:
    calendar = value if isinstance(value, dict) else {}
    weekdays = calendar.get("weekdays") if isinstance(calendar.get("weekdays"), list) else []
    weeks = calendar.get("weeks") if isinstance(calendar.get("weeks"), list) else []
    normalized_weeks: list[list[dict[str, Any]]] = []
    for week in weeks:
        if isinstance(week, list):
            normalized_weeks.append([cell if isinstance(cell, dict) else {"empty": True} for cell in week])
    return {
        "title": str(calendar.get("title") or ""),
        "weekdays": [str(item) for item in weekdays],
        "weeks": normalized_weeks,
    }


def _score_list_entry_data(paths: PluginPaths, entry: ScoreListEntry) -> dict[str, Any]:
    chart = entry.chart
    record = entry.record
    rating = "NEW"
    score: str | int = "NEW"
    acc: float | None = None
    suggest = "---"
    if record is not None:
        rating = _rating_asset(record.rating)
        score = _std_score(record.score)
        acc = record.acc
        suggest = f"RKS {record.rks:.4f}"
    return {
        "song": original._song_display_name(paths, chart.song_id, chart.song_title),
        "composer": original._song_composer(paths, chart.song_id),
        "rank": chart.rank,
        "difficulty": f"{chart.difficulty:.1f}",
        "illustration": original._chart_illustration(paths, chart),
        "acc": acc,
        "suggest": suggest,
        "score": score,
        "Rating": rating,
        "ratingImg": _rating_img(paths, rating),
    }


def _suggest_entry_data(paths: PluginPaths, entry: SuggestEntry) -> dict[str, Any]:
    base = _score_list_entry_data(paths, ScoreListEntry(chart=entry.chart, record=entry.current))
    base["suggest"] = entry.target_acc
    return base


def _phi_suggest_entry_data(paths: PluginPaths, entry: PhiSuggestEntry) -> dict[str, Any]:
    chart = entry.chart
    return {
        "song": original._song_display_name(paths, chart.song_id, chart.song_title),
        "composer": original._song_composer(paths, chart.song_id),
        "level": chart.rank,
        "chart": {chart.rank: {"difficulty": f"{chart.difficulty:.1f}"}},
        "illustration": original._chart_illustration(paths, chart),
        "apCount": int(entry.ap_count),
        "total": int(entry.total or 0),
        "ratingImg": _rating_img(paths, "phi"),
    }


def _table_song_data(paths: PluginPaths, chart: ChartEntry, record: ScoreRecord | None, *, show_score: bool) -> dict[str, Any]:
    score = 0
    if show_score and record is not None:
        score = 100 if record.acc >= 100 else record.acc
    return {
        "rank": chart.rank,
        "illustration": original._chart_illustration(paths, chart),
        "score": score,
        "scoreImg": _rating_img(paths, "phi" if score == 100 else "NEW"),
    }


def _chap_chart_data(paths: PluginPaths, difficulty: float, record: ScoreRecord | None) -> dict[str, Any]:
    if record is None:
        return {
            "difficulty": f"{difficulty:.1f}",
            "Rating": "NEW",
            "ratingImg": _rating_img(paths, "NEW"),
            "suggest": _chap_suggest_text(None, difficulty),
        }
    return {
        "difficulty": f"{difficulty:.1f}",
        "Rating": _rating_asset(record.rating),
        "ratingImg": _rating_img(paths, record.rating),
        "score": _std_score(record.score),
        "acc": f"{record.acc:.4f}",
        "rks": f"{record.rks:.4f}",
        "fc": record.fc,
        "suggest": _chap_suggest_text(record, difficulty),
    }


def _chap_count(summary: Any) -> dict[str, int | str]:
    counts = getattr(summary, "rating_counts", {}) or {}
    result: dict[str, int | str] = {
        "tot": _as_int(getattr(summary, "total_charts", 0)),
    }
    for rating in ("phi", "FC", "V", "S", "A", "B", "C", "F", "NEW"):
        result[_rating_asset(rating)] = _as_int(counts.get(rating))
    return result


def _chap_illustration(paths: PluginPaths, chapter_name: str, records: list[ScoreRecord]) -> str:
    path = paths.original_ill / "chap" / f"{chapter_name}.png"
    uri = original.image_data_uri(paths, path)
    if uri:
        return uri
    if records:
        return original._random_background_for_records(paths, records)
    return original._random_background(paths)


def _chap_suggest_text(record: ScoreRecord | None, difficulty: float) -> str:
    if difficulty <= 0:
        return "无法推分"
    if record is None or record.rks <= 0:
        acc = original._suggest_acc(0.001, difficulty)
    else:
        acc = original._suggest_acc(record.rks + 0.001, difficulty)
    if acc is None:
        return "100.0000%"
    return f"{acc:.4f}%"


def _average_acc_progress(acc_sum: float, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, float(acc_sum) / total))


def _history_b30_row(paths: PluginPaths, change: Any, index: int) -> dict[str, Any]:
    colors = ["#00aaff", "#00f044", "#f0d000", "#ff6161", "#9c9cff"]
    return {
        "date": str(getattr(change, "date", "") or ""),
        "color": colors[index % len(colors)],
        "songs": _history_b30_songs(paths, change),
    }


def _history_b30_songs(paths: PluginPaths, change: Any) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []

    def ensure(record: ScoreRecord) -> dict[str, Any]:
        key = (record.song_id, record.rank)
        if key not in merged:
            order.append(key)
            merged[key] = {
                "ill": original._record_illustration(paths, record),
                "rank": record.rank,
                "newPhi": "",
                "newB27": "",
                "exitPhi": False,
                "exitB27": False,
            }
        return merged[key]

    for index, record in getattr(change, "new_phi", []) or []:
        ensure(record)["newPhi"] = f"P{index}"
    for index, record in getattr(change, "new_b27", []) or []:
        ensure(record)["newB27"] = f"B{index}"
    for record in getattr(change, "exit_phi", []) or []:
        ensure(record)["exitPhi"] = True
    for record in getattr(change, "exit_b27", []) or []:
        ensure(record)["exitB27"] = True
    return [merged[key] for key in order]


def _history_b30_records(changes: list[Any]) -> list[ScoreRecord]:
    records: list[ScoreRecord] = []
    for change in changes:
        records.extend(record for _index, record in getattr(change, "new_phi", []) or [])
        records.extend(record for _index, record in getattr(change, "new_b27", []) or [])
        records.extend(getattr(change, "exit_phi", []) or [])
        records.extend(getattr(change, "exit_b27", []) or [])
    return records


class _LengthList(list[Any]):
    @property
    def length(self) -> int:
        return len(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> "_LengthList":
        return _LengthList(copy.deepcopy(list(self), memo))


def _length_list(value: Any) -> _LengthList:
    return _LengthList(value if isinstance(value, list) else [])


def _pair_rows(pairs: Any, *, key_name: str) -> list[dict[str, str]]:
    if not isinstance(pairs, list):
        return []
    rows: list[dict[str, str]] = []
    for item in pairs[:3]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({key_name: _safe_text(item[0]), "count": _safe_text(item[1])})
        elif isinstance(item, dict):
            rows.append({key_name: _safe_text(item.get(key_name)), "count": _safe_text(item.get("count"))})
    return rows


def _time_rows(pairs: Any) -> list[dict[str, str]]:
    if not isinstance(pairs, list):
        return []
    rows: list[dict[str, str]] = []
    for item in pairs[:3]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append({"day": _safe_text(item[0]), "time": _safe_text(item[1])})
        elif isinstance(item, dict):
            rows.append({"day": _safe_text(item.get("day")), "time": _safe_text(item.get("time"))})
    return rows


def _delta_day(pair_value: Any, *, digits: int) -> dict[str, str]:
    if not pair_value:
        return {"day": "--", "delta": "--"}
    try:
        day, delta = pair_value
    except (TypeError, ValueError):
        return {"day": "--", "delta": "--"}
    return {"day": _safe_text(day), "delta": _format_signed(delta, digits=digits)}


def _data_delta_day(pair_value: Any) -> dict[str, str]:
    if not pair_value:
        return {"day": "--", "deltaBytes": _format_bytes(0)}
    try:
        day, delta = pair_value
    except (TypeError, ValueError):
        return {"day": "--", "deltaBytes": _format_bytes(0)}
    return {"day": _safe_text(day), "deltaBytes": _format_bytes(delta)}


def _history_note_totals(paths: PluginPaths, history: dict[str, Any], catalog: SongCatalog | None) -> dict[str, str]:
    if catalog is None:
        return _empty_note_totals()
    notes = _load_notes_info(paths)
    totals = {"tap": 0, "drag": 0, "hold": 0, "flick": 0, "combo": 0, "time": 0}
    events = iter_history_score_events(history, catalog)
    for event in events:
        note = _note_info(notes, event.record.song_id, event.record.rank)
        song = catalog.get(event.record.song_id)
        chart = song.charts.get(event.record.rank) if song is not None else None
        fallback_combo = _as_int(chart.combo if chart is not None else 0)
        counts = note.get("t") if isinstance(note, dict) else None
        if isinstance(counts, list):
            values = [_as_int(value) for value in counts[:4]]
            while len(values) < 4:
                values.append(0)
        else:
            values = [0, 0, 0, 0]
        totals["tap"] += values[0]
        totals["drag"] += values[1]
        totals["hold"] += values[2]
        totals["flick"] += values[3]
        totals["combo"] += sum(values) or fallback_combo
        totals["time"] += _as_int(note.get("m") if isinstance(note, dict) else 0)
    return {
        "count": _safe_text(len(events)),
        "tap": _safe_text(totals["tap"]),
        "drag": _safe_text(totals["drag"]),
        "hold": _safe_text(totals["hold"]),
        "flick": _safe_text(totals["flick"]),
        "combo": _safe_text(totals["combo"]),
        "time": _seconds_to_hms(totals["time"]),
    }


def _atlas_chart_data(notes: dict[str, Any], song: Song, chart: Any) -> dict[str, Any]:
    note = _note_info(notes, song.id, chart.rank)
    counts = note.get("t") if isinstance(note, dict) else None
    if isinstance(counts, list):
        values = [_as_int(value) for value in counts[:4]]
        while len(values) < 4:
            values.append(0)
    else:
        combo = _as_int(getattr(chart, "combo", 0))
        values = [combo, 0, 0, 0] if combo else [0, 0, 0, 0]
    combo = sum(values) or _as_int(getattr(chart, "combo", 0))
    return {
        "rank": str(getattr(chart, "rank", "") or ""),
        "difficulty": _chart_difficulty_text(chart),
        "level": str(getattr(chart, "level", "") or ""),
        "charter": str(getattr(chart, "charter", "") or ""),
        "rgba": _chart_rgba(chart),
        "tap": values[0],
        "drag": values[1],
        "hold": values[2],
        "flick": values[3],
        "combo": combo or "-",
    }


def _atlas_comment_data(comments: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(comments, dict):
        return None
    rows = [_atlas_comment_row(item) for item in (comments.get("list") or []) if isinstance(item, dict)]
    return {
        "command": str(comments.get("command") or ""),
        "list": rows,
        "total": _as_int(comments.get("total")) or len(rows),
    }


def _atlas_comment_row(item: dict[str, Any]) -> dict[str, Any]:
    rank = str(item.get("rank") or "IN").upper()
    if rank not in LEVELS:
        rank = "IN"
    challenge = _as_int(item.get("challenge") or item.get("challengeModeRank"))
    avatar = str(item.get("avatar") or "Introduction")
    player = str(item.get("PlayerId") or item.get("playerId") or item.get("apiUserId") or "UNKNOWN")
    if len(player) > 15:
        player = player[:12] + "..."
    return {
        "avatar": avatar,
        "PlayerId": player,
        "rks": _as_float(item.get("rks") or item.get("rankingScore")),
        "rank": rank,
        "score": _std_score(item.get("score")),
        "acc": _as_float(item.get("acc")),
        "spInfo": str(item.get("spInfo") or ""),
        "challenge": challenge,
        "time": _date_label(item.get("time") or item.get("createdAt") or item.get("updatedAt")),
        "thisId": str(item.get("thisId") or item.get("id") or "?"),
        "comment": str(item.get("comment") or "").replace("\n", "<br>"),
    }


def _chart_note_info(paths: PluginPaths, song_id: str, rank: str, fallback_combo: int | None) -> dict[str, Any]:
    note = _note_info(_load_notes_info(paths), song_id, rank)
    counts = note.get("t") if isinstance(note, dict) else None
    if isinstance(counts, list):
        values = [_as_int(value) for value in counts[:4]]
        while len(values) < 4:
            values.append(0)
    else:
        combo = _as_int(fallback_combo)
        values = [combo, 0, 0, 0] if combo else [0, 0, 0, 0]
    combo = sum(values) or _as_int(fallback_combo)
    distribution = note.get("d") if isinstance(note, dict) else None
    return {
        "tap": values[0],
        "drag": values[1],
        "hold": values[2],
        "flick": values[3],
        "combo": combo,
        "distribution": _normalize_distribution(distribution, fallback=values),
        "chart_length": _chart_length(note.get("m") if isinstance(note, dict) else None),
    }


def _normalize_distribution(value: Any, *, fallback: list[int] | None = None) -> list[list[float]]:
    if isinstance(value, list):
        rows = []
        for row in value:
            values = list(row) if isinstance(row, list) else []
            values = [_as_float(item) for item in values[:5]]
            while len(values) < 5:
                values.append(0.0)
            rows.append(values)
        if rows:
            return rows
    counts = fallback or [0, 0, 0, 0]
    total = sum(_as_int(item) for item in counts)
    if total <= 0:
        return [[0, 0, 0, 0, 0] for _ in range(12)]
    row = [round(_as_int(value) / total * 100, 2) for value in counts[:4]]
    row.append(100)
    return [row for _ in range(12)]


def _chart_length(value: Any) -> str:
    seconds = _as_int(value)
    if seconds <= 0:
        return "--:--"
    return f"{seconds // 60}:{seconds % 60:02d}"


def _chart_words(tags: dict[str, Any], user_tags: list[str]) -> list[dict[str, Any]]:
    selected = set(str(item) for item in user_tags)
    result = []
    for name, value in sorted(tags.items(), key=lambda item: (-_as_int(item[1]), str(item[0]))):
        text = str(name)
        result.append({
            "name": f"{text} *" if text in selected else text,
            "value": max(1, _as_int(value)),
            "selected": text in selected,
        })
    return result


def _empty_note_totals() -> dict[str, str]:
    return {"count": "0", "tap": "0", "drag": "0", "hold": "0", "flick": "0", "combo": "0", "time": "00h 00m 00s"}


def _load_notes_info(paths: PluginPaths) -> dict[str, Any]:
    path = paths.info / "notesInfo.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _note_info(notes: dict[str, Any], song_id: str, rank: str) -> dict[str, Any]:
    candidates = [song_id, song_id.removesuffix(".0"), f"{song_id}.0" if not song_id.endswith(".0") else song_id]
    for key in candidates:
        value = notes.get(key)
        if isinstance(value, dict):
            rank_data = value.get(rank)
            if isinstance(rank_data, dict):
                return rank_data
    return {}


def _format_signed(value: Any, *, digits: int) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.{digits}f}"


def _chart_difficulty_text(chart: Any) -> str:
    text = str(getattr(chart, "difficulty_text", "") or "")
    if text:
        return text
    difficulty = getattr(chart, "difficulty", None)
    return f"{float(difficulty):.1f}" if difficulty is not None else "?"


def _chart_entry_difficulty_text(chart: ChartEntry, song_chart: Any | None) -> str:
    text = str(getattr(song_chart, "difficulty_text", "") or chart.difficulty_text or "")
    if text:
        return text
    return f"{float(chart.difficulty):.1f}" if chart.difficulty is not None else "?"


def _chart_rgba(chart: Any) -> str:
    rgba = str(getattr(chart, "rgba", "") or "").strip()
    if rgba:
        return rgba
    rank = str(getattr(chart, "rank", "") or "").upper()
    fallback = {
        "EZ": "54, 177, 91, 0.85",
        "HD": "58, 130, 218, 0.85",
        "IN": "211, 72, 129, 0.85",
        "AT": "80, 80, 80, 0.85",
        "LEGACY": "159, 96, 210, 0.85",
    }
    return fallback.get(rank, "128, 128, 128, 0.85")


def _format_bytes(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    sign = "-" if number < 0 else ""
    size = abs(number)
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    if index == 0:
        text = str(int(round(size)))
    else:
        text = f"{round(size, 2):g}"
    return f"{sign}{text}{units[index]}"


def _seconds_to_hms(value: Any) -> str:
    seconds = max(0, _as_int(value))
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


def _safe_text(value: Any) -> str:
    if value is None:
        return "--"
    text = str(value)
    return text if text else "--"


class _ScoreData(list[dict[str, Any]]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__(rows)
        self._by_rank = {str(row.get("rank") or ""): row for row in rows}

    def __deepcopy__(self, memo: dict[int, Any]) -> "_ScoreData":
        return _ScoreData([copy.deepcopy(row, memo) for row in self])

    def __getattr__(self, name: str) -> Any:
        by_rank = self.__dict__.get("_by_rank", {})
        if name in by_rank:
            return by_rank[name]
        raise AttributeError(name)


def _score_data_with_assets(paths: PluginPaths, rows: list[dict[str, Any]]) -> "_ScoreData":
    for row in rows:
        if isinstance(row, dict):
            row["ratingImg"] = _rating_img(paths, row.get("Rating"))
    return _ScoreData(rows)


def _score_template_rank_data(
    rank: str,
    difficulty: float,
    record: ScoreRecord | None,
    phi_rank: int | None,
    best_rank: int | None,
    ap_fc_count: dict[str, Any] | None,
) -> dict[str, Any]:
    if record is None:
        return {
            "rank": rank,
            "difficulty": f"{difficulty:.1f}" if difficulty else "-",
            "Rating": "NEW",
            "suggest": "鏃犳硶鎺ㄥ垎",
            "suggestType": "5",
        }
    suggest, suggest_type = original._score_card_suggest(record)
    return {
        "rank": rank,
        "difficulty": f"{difficulty:.1f}" if difficulty else "-",
        "Rating": _rating_asset(record.rating),
        "score": _std_score(record.score),
        "acc": f"{record.acc:.4f}",
        "rks": f"{record.rks:.4f}",
        "suggest": suggest,
        "suggestType": suggest_type,
        "phiN": min(3, phi_rank) if phi_rank else 0,
        "b19N": min(27, best_rank) if best_rank else 0,
        "apFcCount": _score_ap_fc_count(rank, ap_fc_count),
    }


def _score_ap_fc_count(rank: str, ap_fc_count: dict[str, Any] | None) -> dict[str, Any] | None:
    data = ap_fc_count.get(rank) if isinstance(ap_fc_count, dict) else None
    if not isinstance(data, dict):
        return None
    total = _as_int(data.get("total"))
    if total <= 0:
        return None
    return {
        "ap": _as_int(data.get("apCount")) / total,
        "fc": _as_int(data.get("fcCount")) / total,
        "total": total,
    }


def _score_history_data(item: Any) -> dict[str, Any]:
    if isinstance(item, ScoreRecord):
        return {
            "rank": item.rank,
            "date_new": item.rank,
            "Rating": _rating_asset(item.rating),
            "score_new": _std_score(item.score),
            "acc_new": item.acc,
            "rks_new": item.rks,
        }
    if isinstance(item, dict):
        rating = item.get("Rating") or item.get("rating_new") or item.get("rating") or "NEW"
        return {
            "rank": str(item.get("rank") or ""),
            "date_new": str(item.get("date_new") or item.get("date") or ""),
            "Rating": _rating_asset(str(rating)),
            "score_new": _std_score(item.get("score_new") or item.get("score")),
            "acc_new": _as_float(item.get("acc_new") or item.get("acc")),
            "rks_new": _as_float(item.get("rks_new") or item.get("rks")),
        }
    return {"rank": "", "date_new": "", "Rating": "NEW", "score_new": "", "acc_new": 0.0, "rks_new": 0.0}


def _score_ranklist_data(ranklist: dict[str, Any] | None, selected_rank: str | None) -> dict[str, Any] | None:
    if not isinstance(ranklist, dict):
        return None
    user_rank = _as_int(ranklist.get("userRank"))
    users = ranklist.get("users") if isinstance(ranklist.get("users"), list) else []
    return {
        "userRank": user_rank,
        "totDataNum": _as_int(ranklist.get("totDataNum")),
        "selected": selected_rank or ranklist.get("selected") or "IN",
        "users": [_score_ranklist_user_data(user, user_rank) for user in users[:10] if isinstance(user, dict)],
    }


def _score_ranklist_user_data(item: dict[str, Any], user_rank: int) -> dict[str, Any]:
    gameuser = item.get("gameuser") if isinstance(item.get("gameuser"), dict) else {}
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    challenge = _as_int(gameuser.get("challengeModeRank") or gameuser.get("ChallengeModeRank"))
    index = _as_int(item.get("index"))
    return {
        "index": index,
        "isUser": bool(item.get("isUser")) or (index == user_rank and user_rank > 0),
        "gameuser": {
            "avatar": str(gameuser.get("avatar") or "Introduction"),
            "PlayerId": str(gameuser.get("PlayerId") or gameuser.get("name") or "UNKNOWN"),
            "rankingScore": _as_float(gameuser.get("rankingScore") or gameuser.get("rks")),
            "ChallengeMode": max(0, min(5, challenge // 100)),
            "ChallengeModeRank": challenge % 100,
        },
        "record": {
            "updated_at": original._score_ranklist_date(record.get("updated_at")),
            "acc": _as_float(record.get("acc")),
            "score": _std_score(record.get("score")),
            "Rating": original._score_ranklist_rating(record),
        },
    }


def _update_box_lines(paths: PluginPaths, days: list[Any]) -> list[list[dict[str, Any]]]:
    pending: list[dict[str, Any]] = []
    for day in days:
        changes = getattr(day, "changes", []) or []
        songs = [_update_change_song(paths, change) for change in changes]
        if not songs:
            continue
        pending.append({
            "date": getattr(day, "date", ""),
            "color": _random_update_title_color(),
            "update_num": getattr(day, "update_count", 0),
            "song": songs,
        })
    box_line: list[list[dict[str, Any]]] = []
    line_num = 5
    continued_day = False
    while pending:
        day = pending[0]
        if line_num == 5:
            entry = _update_box_segment(day, 5, include_date=not continued_day)
            box_line.append([entry])
            line_num = len(entry["song"])
        else:
            entry = _update_box_segment(day, 5 - line_num, include_date=not continued_day)
            box_line[-1].append(entry)
            line_num += len(entry["song"])
        continued_day = True
        if not day["song"]:
            entry["update_num"] = day["update_num"]
            pending.pop(0)
            continued_day = False
    return box_line


def _update_box_segment(day: dict[str, Any], limit: int, *, include_date: bool) -> dict[str, Any]:
    songs = day["song"][:limit]
    del day["song"][:limit]
    entry = {
        "color": day["color"],
        "update_num": 0,
        "width": _update_segment_width(len(songs)),
        "song": songs,
    }
    if include_date:
        entry["date"] = day["date"]
    return entry


def _update_segment_width(count: int) -> int:
    return max(135, count * 135 + 20 * count - 20)


def _random_update_title_color() -> str:
    return "#" + "".join(f"{random.randint(0, 200):02x}" for _ in range(3))


def _update_change_song(paths: PluginPaths, change: Any) -> dict[str, Any]:
    return {
        "illustration": original._record_illustration(paths, change),
        "song": getattr(change, "song_title", ""),
        "rank": getattr(change, "rank", ""),
        "score_new": _std_score(getattr(change, "score_new", 0)),
        "acc_new": _as_float(getattr(change, "acc_new", 0)),
        "rks_new": _as_float(getattr(change, "rks_new", 0)),
        "Rating": _rating_asset(str(getattr(change, "rating_new", "") or "")),
        "isB19": "",
    }


def _first_record_task(paths: PluginPaths, summary: UpdateProgressSummary) -> list[dict[str, Any] | None]:
    if not summary.is_first_record:
        return []
    return [{
        "song": "首次记录",
        "illustration": original.asset_uri(paths, "html/otherimg/data.png"),
        "request": {"rank": "INFO", "value": "首次记录"},
        "reward": 0,
        "finished": True,
    }]


def _series_lines(
    history: dict[str, Any],
    key: str,
    *,
    current: tuple[str, Any] | None = None,
    money: bool = False,
) -> tuple[list[list[float]], list[float], list[str]]:
    raw_series = history.get(key) if isinstance(history.get(key), list) else []
    points: list[tuple[datetime, float]] = []
    for item in raw_series:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        number = money_to_kib(value) if money else _as_float(value)
        date = _series_datetime(item.get("date"))
        if date is not None and number is not None:
            points.append((date, float(number)))
    if current is not None:
        current_number = money_to_kib(current[1]) if money else _as_float(current[1])
        current_date = _series_datetime(current[0])
        if current_date is not None and current_number is not None and not any(date == current_date for date, _ in points):
            points.append((current_date, float(current_number)))
    points.sort(key=lambda item: item[0])
    if not points:
        return [], [0.0, 0.0], ["", ""]
    compacted, value_range = _compact_series_points(points)
    date_range = [compacted[0][0].timestamp(), compacted[-1][0].timestamp()]
    lines = _numeric_series_to_lines([(date.timestamp(), value) for date, value in compacted], value_range=value_range, x_range=date_range)
    if not lines and compacted:
        lines = [[0.0, 50.0, 100.0, 50.0]]
    return lines, value_range, [_format_series_date(compacted[0][0]), _format_series_date(compacted[-1][0])]


def _compact_series_points(points: list[tuple[datetime, float]]) -> tuple[list[tuple[datetime, float]], list[float]]:
    compacted: list[tuple[datetime, float]] = []
    value_range = [float("inf"), 0.0]
    for index, item in enumerate(points):
        if index <= 1 or not compacted or item[1] != compacted[-2][1]:
            compacted.append(item)
            value_range[0] = min(value_range[0], item[1])
            value_range[1] = max(value_range[1], item[1])
        else:
            compacted[-1] = item
    if value_range[0] == float("inf"):
        value_range = [0.0, 0.0]
    return compacted, value_range


def _numeric_series_to_lines(
    points: list[tuple[float, float]],
    *,
    value_range: list[float] | None = None,
    x_range: list[float] | None = None,
) -> list[list[float]]:
    if len(points) < 2:
        return []
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    x_bounds = x_range or [min(xs), max(xs)]
    y_bounds = value_range or [min(ys), max(ys)]
    min_x, max_x = x_bounds[0], x_bounds[-1]
    min_y, max_y = y_bounds[0], y_bounds[-1]
    result: list[list[float]] = []
    for left, right in zip(points, points[1:]):
        x1 = _range_percent(left[0], [min_x, max_x])
        x2 = _range_percent(right[0], [min_x, max_x])
        y1 = _range_percent(left[1], [min_y, max_y])
        y2 = _range_percent(right[1], [min_y, max_y])
        result.append([x1, y1, x2, y2])
    return result


def _range_percent(value: float, bounds: list[float]) -> float:
    start = float(bounds[0])
    end = float(bounds[-1])
    if start == end:
        return 50.0
    return abs((float(value) - start) / (end - start) * 100)


def _series_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone().replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for candidate in (
            text,
            text.replace("Z", "+00:00"),
            text.replace("/", "-"),
        ):
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo is not None else parsed
            except ValueError:
                continue
    return None


def _format_series_date(value: datetime) -> str:
    return format_datetime(value)


def _date_label(value: Any) -> str:
    parsed = _series_datetime(value)
    if parsed is not None:
        return _format_series_date(parsed)
    return str(value or "")


def _signed_delta(value: int | float | None, *, digits: int = 4, suffix: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:+.{digits}f}"
    else:
        text = f"{value:+d}"
    return f"{text}{suffix}"


def _format_money(money: list[int] | None) -> str:
    if not money:
        return "0KiB"
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    return " ".join(f"{value}{unit}" for value, unit in reversed(list(zip(money, units))) if value) or "0KiB"


def _info_intro(snapshot: SaveSnapshot, summary: UserSummary) -> str:
    raw_user = snapshot.raw.get("gameuser") if isinstance(snapshot.raw.get("gameuser"), dict) else {}
    intro = raw_user.get("selfIntro")
    if intro:
        return str(intro)
    return f"Total Records: {summary.total_records}"


def _info_background(paths: PluginPaths, snapshot: SaveSnapshot) -> str:
    raw_user = snapshot.raw.get("gameuser") if isinstance(snapshot.raw.get("gameuser"), dict) else {}
    song_id = str(raw_user.get("background") or "")
    if not song_id or song_id.casefold() == "introduction":
        return original.asset_uri(paths, "html/otherimg/phigros.png") or original._random_background(paths)
    if song_id:
        path = find_background_illustration_file(paths, song_id)
        if path is not None:
            return original._illustration_source(paths, path, song_id=song_id, background=True)
        if use_remote_illustrations(paths) and is_known_online_illustration_id(paths, song_id):
            return background_illustration_url(song_id, paths=paths)
    return original.asset_uri(paths, "html/otherimg/phigros.png") or original._random_background(paths)


def _info_stats(snapshot: SaveSnapshot, catalog: SongCatalog | None) -> dict[str, dict[str, Any]]:
    by_rank: dict[str, dict[str, Any]] = {
        rank: {
            "unlock": 0,
            "total": 0,
            "cleared": 0,
            "fc": 0,
            "phi": 0,
            "score": 0,
            "tot_score": 0,
            "highest": 0.0,
            "lowest": 18.0,
            "rating": "",
        }
        for rank in LEVELS
    }
    if catalog is not None:
        for song in catalog.all_songs():
            for chart in song.display_charts():
                if chart.rank not in by_rank:
                    continue
                if _as_float(getattr(chart, "difficulty", 0.0)) <= 0:
                    continue
                item = by_rank[chart.rank]
                item["total"] += 1
        raw_records = snapshot.raw.get("gameRecord")
        if isinstance(raw_records, dict):
            for raw_song_id, level_records in raw_records.items():
                song = catalog.get(str(raw_song_id))
                if song is None:
                    continue
                for index, record_data in _iter_info_level_records(level_records):
                    if index >= len(ALL_LEVELS):
                        continue
                    rank = ALL_LEVELS[index]
                    if rank not in by_rank:
                        continue
                    by_rank[rank]["unlock"] += 1
                    if not isinstance(record_data, dict):
                        continue
                    chart = song.charts.get(rank)
                    difficulty = _as_float(getattr(chart, "difficulty", 0.0)) if chart is not None else 0.0
                    _apply_info_record_stat(by_rank[rank], record_data, difficulty)
    for rank, item in by_rank.items():
        if item["lowest"] == 18.0:
            item["lowest"] = 0.0
        item["rating"] = _aggregate_rating(item["score"], item["fc"] == item["unlock"], item["tot_score"])
    return by_rank


def _info_userstats_list(stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rank in LEVELS:
        item = stats.get(rank, {})
        result.append({
            "title": rank,
            "tatle": rank,
            "Rating": item.get("rating", "V"),
            "unlock": item.get("unlock", 0),
            "tot": item.get("total", 0),
            "cleared": item.get("cleared", 0),
            "fc": item.get("fc", 0),
            "phi": item.get("phi", 0),
            "real_score": item.get("score", 0),
            "tot_score": item.get("tot_score", 0),
            "highest": float(item.get("highest", 0.0)),
            "lowest": float(item.get("lowest", 0.0)),
        })
    return result


def _apply_info_record_stat(item: dict[str, Any], record_data: dict[str, Any], difficulty: float) -> None:
    score = _as_int(record_data.get("score"))
    acc = _as_float(record_data.get("acc"))
    fc = bool(record_data.get("fc"))
    rks = _as_float(record_data.get("rks")) if record_data.get("rks") is not None else rks_from_acc(acc, difficulty)
    if score >= 700_000:
        item["cleared"] += 1
    if fc or score >= 1_000_000:
        item["fc"] += 1
    if score >= 1_000_000:
        item["phi"] += 1
    item["score"] += score
    item["tot_score"] += 1_000_000
    item["highest"] = max(float(item["highest"]), rks)
    item["lowest"] = min(float(item["lowest"]), rks)


def _iter_info_level_records(value: Any):
    if isinstance(value, list):
        yield from enumerate(value)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            try:
                yield int(key), item
            except (TypeError, ValueError):
                continue


def _aggregate_rating(real_score: int, fc: bool, tot_score: int) -> str:
    if real_score == tot_score:
        return "phi"
    if fc:
        return "FC"
    if real_score >= tot_score * 0.96:
        return "V"
    if real_score >= tot_score * 0.92:
        return "S"
    if real_score >= tot_score * 0.88:
        return "A"
    if real_score >= tot_score * 0.82:
        return "B"
    if real_score >= tot_score * 0.70:
        return "C"
    if real_score > 0:
        return "F"
    return "NEW"


def _info_acc_rks(snapshot: SaveSnapshot, catalog: SongCatalog | None) -> tuple[list[list[float]], list[float], list[list[float]]]:
    if catalog is None:
        return [], [0.0, 1.0], []
    records = sorted(iter_score_records(snapshot, catalog), key=lambda item: item.rks, reverse=True)
    phi_records = sorted((record for record in records if record.acc >= 100), key=lambda item: item.rks, reverse=True)[:3]
    phi_rks = sum(record.rks for record in phi_records)
    acc_records = list(records)
    b27_source = acc_records[:27]
    if not b27_source:
        return [], [0.0, 1.0], []
    min_acc = min(record.acc for record in b27_source)
    acc_range: list[float] = [100.0]
    for record in b27_source:
        acc_range[0] = min(acc_range[0], record.acc)
    samples: list[tuple[float, float]] = []
    value_range = [100.0, 0.0]
    threshold = acc_range[0]
    while threshold <= 100.0:
        sum_rks = 0.0
        if not acc_records:
            break
        index = 0
        while index < len(acc_records) and index < 27:
            if acc_records[index].acc < threshold:
                acc_range.append(threshold)
            while index < len(acc_records) and acc_records[index].acc < threshold:
                acc_records.pop(index)
            if index < len(acc_records):
                sum_rks += acc_records[index].rks
            else:
                break
            index += 1
        rks = (sum_rks + phi_rks) / 30
        samples.append((threshold, rks))
        value_range[0] = min(value_range[0], rks)
        value_range[1] = max(value_range[1], rks)
        threshold += 0.01
    if acc_range[-1] < 100:
        acc_range.append(100.0)
    lines = _acc_rks_lines(samples, value_range, acc_range)
    labels = _acc_range_labels(acc_range)
    return lines, value_range, labels


def _acc_rks_lines(
    samples: list[tuple[float, float]],
    value_range: list[float],
    acc_range: list[float],
) -> list[list[float]]:
    lines: list[list[float]] = []
    for previous, current in zip(samples, samples[1:]):
        if lines and previous[1] == current[1]:
            lines[-1][2] = _range_percent(current[0], acc_range)
        else:
            lines.append([
                _range_percent(previous[0], acc_range),
                _range_percent(previous[1], value_range),
                _range_percent(current[0], acc_range),
                _range_percent(current[1], value_range),
            ])
    return lines


def _acc_range_labels(acc_range: list[float]) -> list[list[float]]:
    values = list(acc_range)
    if not values:
        return []
    if values[0] == 100:
        values[0] = 0.0
    acc_length = 100.0 - values[0]
    if acc_length <= 0:
        return [[values[0], 0.0]]
    while len(values) >= 2 and 100.0 - values[-2] < acc_length / 10:
        values.pop(-2)
    min_acc = values[0]
    labels = [[values[0], 0.0]]
    index = 1
    while index < len(values):
        while index < len(values) and values[index] - values[index - 1] < acc_length / 10:
            values.pop(index)
        if index >= len(values):
            break
        labels.append([values[index], (values[index] - min_acc) / acc_length * 100])
        index += 1
    return labels


def _ensure_length(value: Any, length: int, default: Any) -> list[Any]:
    result = list(value) if isinstance(value, list) else []
    while len(result) < length:
        result.append(default)
    return result[:length]


def _acc_avg_value(record: ScoreRecord, *, phi: bool) -> float | str | None:
    if record.acc_avg is None:
        return None
    if phi:
        return record.acc_avg
    return f"Avg: {record.acc_avg:.4f}%"


def _b30_sp_info(paths: PluginPaths, result: Best30Result, snapshot: SaveSnapshot) -> list[str]:
    info: list[str] = []
    latest = latest_version_log(paths.info)
    save_version = _as_int(snapshot.game_version)
    if latest is not None and save_version and save_version < latest.version_code:
        save_log = load_version_log(paths.info, save_version)
        info.append(f"{save_log.version_label if save_log else save_version} Update to {latest.version_label}")
        info.append(f"Real RKS: {result.computed_rks:.4f}")
    elif abs(result.computed_rks - result.official_rks) > 1e-4:
        info.append(f"Real RKS: {result.computed_rks:.4f}")
    return info


def _std_score(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value or "")


def _notice_date_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp).strftime("%m-%d")
    except (TypeError, ValueError, OSError):
        return str(value)


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _dominant_rating(counts: dict[str, int]) -> str:
    order = {"NEW": 0, "F": 1, "C": 2, "B": 3, "A": 4, "S": 5, "V": 6, "FC": 7, "PHI": 8, "phi": 8}
    values = [(key, value) for key, value in counts.items() if value]
    if not values:
        return "NEW"
    rating = max(values, key=lambda item: (item[1], order.get(str(item[0]), -1)))[0]
    return "phi" if rating == "PHI" else str(rating)


def _rating_asset(value: str) -> str:
    text = str(value or "NEW")
    if text in {"PHI", "AP"}:
        return "phi"
    return text


def _suggest_type(acc: float) -> int:
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


def _range_bounds(range_text: str, fallback_low: float, fallback_high: float) -> tuple[str, str]:
    text = str(range_text or "")
    if "-" in text:
        left, right = text.split("-", 1)
        return left.strip(), right.strip()
    return f"{fallback_low:g}", f"{fallback_high:g}"


def _percentage(value: int | float, total: int | float) -> float:
    try:
        total_f = float(total)
        if total_f <= 0:
            return 0.0
        return max(0.0, min(100.0, float(value) / total_f * 100.0))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


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
