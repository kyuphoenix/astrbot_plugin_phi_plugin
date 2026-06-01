from __future__ import annotations

import html
import json
import base64
import csv
import hashlib
import mimetypes
import math
import random
import re
import urllib.request
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from ..data.loader import SongCatalog
from ..data.loader import normalize_key as normalize_song_key
from ..data.illustrations import (
    background_illustration_url,
    background_source_candidates,
    find_background_illustration_file,
    find_illustration_file,
    illustration_url,
    is_known_online_illustration_id,
    is_online_illustration_url,
    online_url_for_local_path,
    use_remote_illustrations,
)
from ..data.resources import VersionLog, latest_version_log, load_version_log
from ..models import (
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
)
from ..models import ProgressDay, ProgressScoreChange, UpdateProgressSummary, UserSummary
from ..paths import PluginPaths
from ..query.b30 import iter_score_records
from ..query.progress import extract_modified_datetime, extract_money, format_datetime, money_to_kib

_CSS_URL_RE = re.compile(r"url\((['\"]?)([^)'\"]+)\1\)")
_CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\()?['\"]([^'\")]+)['\"]\)?\s*;")


def help_html(paths: PluginPaths, *, cmd_head: str = "phi") -> str:
    help_path = paths.info / "help.json"
    groups = json.loads(help_path.read_text(encoding="utf-8")) if help_path.exists() else []
    body: list[str] = []
    for group in groups:
        items = group.get("list") if isinstance(group, dict) else None
        if not isinstance(items, list):
            continue
        body.append('<div class="help_box">')
        body.append(f'<div class="help-group">——·{_esc(group.get("group", ""))}·——</div>')
        for index, item in enumerate(items, 1):
            title = _command_text(str(item.get("title") or ""), cmd_head)
            example = _command_text(str(item.get("eg") or item.get("title") or ""), cmd_head)
            desc = _command_text(str(item.get("desc") or ""), cmd_head).replace(" ", "&ensp;")
            body.append('<div class="line">')
            body.append(f'<div class="order"><p name="pvis">{title}</p></div>')
            body.append('<div class="info_box"><div class="up">')
            body.append(f'<div class="num">{index}</div><div class="song"><p name="pvis">{example}</p></div>')
            body.append('</div><div class="down"><div class="desc">')
            if desc:
                body.append(f'<p name="pvis">{desc}</p>')
            if item.get("img"):
                body.append(f'<img src="{asset_uri(paths, "html/otherimg/" + str(item["img"]))}" alt="{_esc(str(item["img"]))}">')
            body.append("</div></div></div></div>")
        body.append("</div>")
    body.append('<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>')
    return original_page(paths, "help/help.css", "\n".join(body), theme="default", background=_random_background(paths))


def b30_html(paths: PluginPaths, result: Best30Result, snapshot: SaveSnapshot) -> str:
    records = result.records
    phi_records = result.phi_records[:3] or [record for record in records if record.acc >= 100][:3]
    b_records = records
    stats = _level_stats(records)
    gameuser = _gameuser(snapshot)
    date_text = format_datetime(extract_modified_datetime(snapshot.raw))
    background = _random_background_for_records(paths, [*phi_records, *records])

    body: list[str] = [_b30_title(paths, gameuser, stats, date_text, _b30_sp_info(paths, result, snapshot))]
    body.append('<div class="b19">')
    for index, record in enumerate(phi_records, 1):
        body.append(_b30_record_card(paths, record, f"P{index}", phi=True))
    for index, record in enumerate(b_records, 1):
        if index == 28:
            body.append(_overflow_html())
        body.append(_b30_record_card(
            paths,
            record,
            f"#{index}",
            phi=False,
            b_score=index <= 27,
            suggest=_record_suggest(result, record, index),
        ))
    body.append("</div>")
    return original_page(paths, "b19/b19.css", "\n".join(body), theme="default", background=background)


def record_list_html(
    paths: PluginPaths,
    records: list[ScoreRecord],
    snapshot: SaveSnapshot,
    *,
    title: str,
    sp_info: list[str] | None = None,
    limit_label: str = "B",
) -> str:
    gameuser = _gameuser(snapshot)
    gameuser["rks"] = _record_list_rks(records)
    background = _random_background_for_records(paths, records)
    header_ill = _record_illustration(paths, records[0]) if records else background
    body: list[str] = [_dss2_title(paths, gameuser, title, header_ill, sp_info or [])]
    main_records = records[:30]
    overflow_records = records[30:]
    body.append(f'<div class="label clip-box-right"><p class="skew weight-font">{_esc(limit_label)}{len(main_records)}</p></div>')
    body.append('<div class="content-box">')
    for index, record in enumerate(main_records, 1):
        body.append(_dss2_record_card(paths, record, f"{limit_label}{index}", highlighted=index <= 27))
    body.append("</div>")
    if overflow_records:
        body.append('<div class="label clip-box-right"><p class="skew weight-font">OVERFLOW</p></div>')
        body.append('<div class="content-box">')
        for index, record in enumerate(overflow_records, 31):
            body.append(_dss2_record_card(paths, record, f"{limit_label}{index}", highlighted=False))
        body.append("</div>")
    body.append('<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>')
    return original_page(paths, "b19/dss2.css", "\n".join(body), theme="default", background=background)


def list_html(paths: PluginPaths, entries: list[ScoreListEntry], *, title: str = "Score List", limit: int = 80) -> str:
    rows = []
    for index, entry in enumerate(entries[:limit], 1):
        rows.append(_score_list_line(paths, entry, index))
    if len(entries) > limit:
        rows.append(_notice_line(f"... 还有 {len(entries) - limit} 条未显示，请缩小筛选范围。"))
    if not rows:
        rows.append(_notice_line("没有找到符合条件的谱面或成绩。"))
    body = f"""
<div class="head_title"><p>{_esc(title)}</p></div>
<div class="list_box">
  {''.join(rows)}
</div>
<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
"""
    return original_page(paths, "list/list.css", body, theme="default", background=_random_background_for_entries(paths, entries))


def suggest_html(
    paths: PluginPaths,
    entries: list[SuggestEntry],
    *,
    phi_entries: list[PhiSuggestEntry] | None = None,
    title: str = "推分建议",
) -> str:
    grouped: dict[str, list[SuggestEntry]] = {str(index): [] for index in range(6)}
    for entry in entries:
        grouped[_suggest_type(entry.target_acc)].append(entry)
    groups = [
        ("5", "99.85% ~ 100%"),
        ("4", "99.70% ~ 99.85%"),
        ("3", "99.50% ~ 99.70%"),
        ("2", "99.00% ~ 99.50%"),
        ("1", "98.50% ~ 99.00%"),
        ("0", "00.00% ~ 98.50%"),
    ]
    body_parts = [f'<div class="head_title"><p>{_esc(title)}</p></div>', '<div class="group_list">']
    body_parts.append('<div class="group group-phi"><div class="group_title"><p>phi</p></div><div class="row_box">')
    for index, entry in enumerate(phi_entries or [], 1):
        body_parts.append(_phi_suggest_line(paths, entry, index))
    body_parts.append("</div></div>")
    for key, label in groups:
        body_parts.append(f'<div class="group group-kind-{key}"><div class="group_title"><p>{_esc(label)}</p></div><div class="row_box">')
        if grouped[key]:
            for index, entry in enumerate(grouped[key], 1):
                body_parts.append(_suggest_line(paths, entry, index, key))
        body_parts.append("</div></div>")
    if not entries:
        body_parts.append('<div class="group"><div class="row_box">')
        body_parts.append(_notice_line("暂时没有找到可推分建议。"))
        body_parts.append("</div></div>")
    body_parts.append("</div>")
    body_parts.append('<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>')
    return original_page(paths, "suggest/suggest.css", "\n".join(body_parts), theme="default", background=_random_background_for_suggestions(paths, entries))


def table_html(
    paths: PluginPaths,
    charts: list[ChartEntry],
    *,
    difficulty: float,
    version_label: str = "current",
    snapshot: SaveSnapshot | None = None,
) -> str:
    record_map: dict[tuple[str, str], ScoreRecord] = {}
    return table_with_records_html(paths, charts, difficulty=difficulty, version_label=version_label, record_map=record_map, snapshot=snapshot)


def table_with_records_html(
    paths: PluginPaths,
    charts: list[ChartEntry],
    *,
    difficulty: float,
    version_label: str = "current",
    record_map: dict[tuple[str, str], ScoreRecord] | None = None,
    snapshot: SaveSnapshot | None = None,
) -> str:
    grouped: dict[str, list[ChartEntry]] = {}
    for chart in sorted(charts, key=lambda item: (item.difficulty, item.rank, item.song_title)):
        grouped.setdefault(f"{chart.difficulty:.1f}", []).append(chart)
    gameuser = _gameuser(snapshot) if snapshot is not None else None
    body = [
        '<div class="row titleRow"><div class="title"><div class="phigrosTitle"><p class="phigros-title-font">Phigros</p></div>'
        '<div class="title-line"><div class="titleDesc"><p>Constant Table</p></div>'
        f'<div class="phigrosVersion clip-box"><p>{_esc(version_label)}</p></div></div></div>'
        '<div class="queryDifficulty"><div class="qdBox"><div class="query"><p>Difficulty</p></div>'
        f'<div class="total"><p>Total: {len(charts)}</p></div><div class="index clip-box"><div class="query"><p>Difficulty</p></div><p>{difficulty:g}</p>'
        f'<div class="total"><p>Total: {len(charts)}</p></div></div></div></div></div>'
    ]
    if gameuser is not None:
        body.append('<div class="row playerInfoRow">')
        body.append(_table_player_info(paths, gameuser, format_datetime(extract_modified_datetime(snapshot.raw))))
        body.append("</div>")
    body.append('<div class="tableBox">')
    for label, label_charts in grouped.items():
        min_rating = _table_bucket_rating(label_charts, record_map or {})
        body.append('<div class="label"><div class="labelHead"><div class="heng"><div class="line clip-box"></div></div><div class="shu leftSlopeAbsolute"><div class="line clip-box"></div></div></div>')
        body.append(f'<div class="labelContentBox"><div class="labelContent clip-box"><p>{_esc(label)}</p></div>')
        if gameuser is not None:
            body.append(f'<div class="labelContent clip-box"><img src="{asset_uri(paths, f"html/otherimg/{min_rating}.png")}" alt="{_esc(min_rating)}"></div>')
        body.append("</div></div>")
        body.append('<div class="content">')
        for chart in label_charts:
            body.append(_table_chart_card(paths, chart, (record_map or {}).get((chart.song_id, chart.rank)), show_score=gameuser is not None))
        body.append("</div>")
    body.append("</div>")
    body.append('<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>')
    return original_page(paths, "table/table.css", "\n".join(body), theme="default", background=_random_background_for_charts(paths, charts))


def lvscore_html(paths: PluginPaths, summary: LevelScoreSummary, snapshot: SaveSnapshot) -> str:
    gameuser = _gameuser(snapshot)
    challenge_img = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    rating = _dominant_rating_from_counts(summary.rating_counts)
    rating_img = asset_uri(paths, f"html/otherimg/{rating}.png")
    progress_phi = _percentage(summary.phi_count, summary.total_charts)
    progress_fc = _percentage(summary.fc_count, summary.total_charts)
    rank_boxes = "".join(_lvscore_rank_box(rank, summary.rank_counts.get(rank, 0)) for rank in ("AT", "IN", "HD", "EZ"))
    rating_stats = "".join(
        f'<div class="rating_stats_group"><img src="{asset_uri(paths, f"html/otherimg/{_rating_asset(rating_key)}.png")}" alt="{_esc(_rating_asset(rating_key))}"><p>{count}</p><div class="rating_stats_bar" style="height:{_percentage(count, max(summary.rating_counts.values()) if summary.rating_counts else 1)}%;"></div></div>'
        for rating_key, count in summary.rating_counts.items()
        if rating_key != "tot" and count
    )
    body = f"""
<div class="full-box">
  <div class="left">
    <div class="left-top"><img src="{_random_background(paths)}" alt="illustration"></div>
    <div class="left-content"><div class="left-content-left"></div><div class="left-content-right"></div></div>
    <div class="left-mid">{rank_boxes}</div>
    <div class="left-mid-bottom"></div>
    <div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
  </div>
  <div class="left-up">
    <div class="left-top">
      <div class="illustration"><img src="{_random_background(paths)}" alt="illustration"></div>
      <div class="user_info"><div class="info_up">
        <div class="avatar"><img src="{asset_uri(paths, f"html/avatar/{gameuser['avatar']}.png") or asset_uri(paths, "html/avatar/Introduction.png")}" alt="{_esc(gameuser['avatar'])}"></div>
        <div class="basic_info"><div class="user_name"><p name="pvis">{_esc(gameuser['PlayerId'])}</p></div><div class="user_rks"><div class="player_rks"><p>{float(gameuser['rks']):.4f}</p></div><div class="Challenge"><img src="{challenge_img}" alt="Challenge"><p>{gameuser['ChallengeModeRank']}</p></div></div></div>
        <div class="user_info_right"></div>
      </div></div>
      <div class="difficulty_box"><div class="difficulty_box_p"><p>已选定数区间</p></div><div class="difficulty_value" style="margin-left:0%;"><p>{_esc(summary.range_text.split('-', 1)[0])}</p></div><div class="difficulty_bar-out"><div class="difficulty_bar-in" style="margin-left:0%;width:100%;"></div></div><div class="difficulty_value" style="margin-left:100%;"><p>{_esc(summary.range_text.split('-', 1)[-1])}</p></div></div>
    </div>
    <div class="left-content"><div class="left-content-left"><p>CONTENT</p></div><div class="left-content-right"></div></div>
    <div class="left-mid">{rank_boxes.replace("left-mid-box", "left-up-mid-box")}</div>
    <div class="left-up-mid-bottom"></div>
  </div>
  <div class="right" id="{_esc(_rating_asset(rating))}">
    <div class="file-content"><div class="file-content-left"><p>FILE_CONTENT</p></div><div class="progress_bar-out"><div class="progress_bar-in-phi" style="width:{progress_phi:.4f}%;"><p>{progress_phi:.4f}% PHI.</p></div><div class="progress_bar-in-fc" style="width:{max(0.0, progress_fc - progress_phi):.4f}%;"><p>{progress_fc:.4f}% FullCombo.</p></div></div></div>
    <div class="right_title"><p>Total</p><div class="title_group"><div class="title_group-real"><p>{summary.played_charts}</p></div><div class="title_group-tot"><p>/{summary.total_charts} charts</p></div></div></div>
    <div class="right_content"><div class="right_content-title"><p>收集日期</p></div><p>{_esc(format_datetime(extract_modified_datetime(snapshot.raw)))}</p><div class="right_content-title"><p>保管单位</p></div><p>{_esc(gameuser['PlayerId'])}</p><div class="right_content-title"><p>定数范围</p></div><p>{_esc(summary.range_text)}</p></div>
    <div class="tot_Rating"><img src="{rating_img}" alt="{_esc(rating)}"></div>
    <div class="title_group" id="score"><div class="title_group-real" id="real-score"><p>{int(summary.avg_score):,}</p></div><div class="title_group-tot" id="tot-score"><p>avg score</p></div></div>
    <div class="title_group" id="highest"><div class="title_group-real" id="real-highlow"><p>{summary.highest_difficulty:.4f}</p></div><div class="title_group-tot" id="tot-highlow"><p>Highest</p></div></div>
    <div class="title_group" id="lowest"><div class="title_group-real" id="real-highlow"><p>{summary.lowest_difficulty:.4f}</p></div><div class="title_group-tot" id="tot-highlow"><p>Lowest</p></div></div>
    <div class="tot_acc-box"><div class="tot_acc-left"><span>{int(summary.avg_acc)}</span></div><div class="tot_acc-right"><span id="acc_word">ACC</span><span>.{int((summary.avg_acc % 1) * 10000):04d}%</span></div></div>
    <div class="stats-rating-group"><div class="rating-group"><div class="rating-value"><p>{summary.played_charts}</p></div><div class="rating-tatle"><p>Cleared</p></div></div><div class="rating-group"><div class="rating-value"><p>{summary.fc_count}</p></div><div class="rating-tatle"><p>FC</p></div></div><div class="rating-group"><div class="rating-value"><p>{summary.phi_count}</p></div><div class="rating-tatle"><p>PHI</p></div></div></div>
    <div class="rating_stats">{rating_stats}</div>
  </div>
</div>
"""
    return original_page(paths, "lvsco/lvsco.css", body, theme="default", background=_random_background(paths))


def score_html(
    paths: PluginPaths,
    song: Song,
    records: list[ScoreRecord],
    snapshot: SaveSnapshot,
    *,
    history: list[ScoreRecord] | None = None,
    ranklist: dict[str, Any] | None = None,
    selected_rank: str | None = None,
    ap_fc_count: dict[str, Any] | None = None,
) -> str:
    gameuser = _gameuser(snapshot)
    illustration = _song_illustration(paths, song)
    challenge_img = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    score_cards = []
    record_map = {record.rank: record for record in records}
    for rank in LEVELS:
        chart = song.charts.get(rank)
        if chart is None:
            continue
        score_cards.append(_score_rank_card(paths, rank, chart.difficulty or 0.0, record_map.get(rank), ap_fc_count))
    history_rows = "".join(_score_history_row(paths, record) for record in (history or records)[:12])
    ranklist_panel = _score_ranklist_panel(paths, ranklist, selected_rank) if ranklist else ""
    body = f"""
<div class="left">
  <div class="Player_Info"><p>PLAYER & SONGS_INFO</p></div>
  <div class="basic-box">
    <div class="song_Id"><p name="pvis">{_esc(song.title)}</p></div>
    <div class="basic-img"><img src="{illustration}" alt="{_esc(song.title)}"></div>
    <div class="Player_Id">
      <div class="avatar"><img src="{asset_uri(paths, f"html/avatar/{gameuser['avatar']}.png") or asset_uri(paths, "html/avatar/Introduction.png")}" alt="{_esc(gameuser['avatar'])}"></div>
      <div class="Player_Id-box"><div class="Player_Id-left"><p>ID</p></div><div class="Player_Id-right"><p name="pvis">{_esc(gameuser['PlayerId'])}</p></div></div>
    </div>
  </div>
  <div class="left_title"><div class="left_title-left"><p>PLAYER_DETAIL</p></div></div>
  <div class="Player_data_line">
    <div class="Player_data_line-left"><div class="Player_data_title" id="Player_data_left"><p>RKS</p></div><div class="Player_data_value" id="Player_data_left"><p>{float(gameuser['rks']):.4f}</p></div></div>
    <div class="Player_data_line-right"><div class="Player_data_title" id="Player_data_right"><p>CLG MOD</p></div><div class="Challenge" id="Challenge2"><img src="{challenge_img}" alt="Challenge"><span>{gameuser['ChallengeModeRank']}</span></div></div>
  </div>
  <div class="left_title"><div class="left_title-left"><p>SONG_DETAIL</p></div></div>
  <div class="rank_dif_{1 if song.charts.get('AT') else 0}">
    {''.join(_score_difficulty_chip(rank, song.charts[rank].difficulty or 0.0) for rank in LEVELS if rank in song.charts)}
  </div>
  <div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
</div>
<div class="right">
  <div class="file-content"><div class="file-content-left"><p>SCORE_DATA</p></div></div>
  <div class="data_title"><div class="data_title-left"><p>SCORE_INFO</p></div></div>
  <div class="stats-box">{''.join(score_cards)}</div>
  <div class="data_title"><div class="data_title-left"><p>SCORE_HISTORY</p></div></div>
  <div class="scoreHistory">{history_rows or '<div class="oneHistory EZ"><div class="HistoryDate"><p>NO HISTORY</p></div></div>'}</div>
</div>
{ranklist_panel}
"""
    css = ("userinfo/userinfo.css", "score/score.css", "score/scoreRankList.css") if ranklist else ("userinfo/userinfo.css", "score/score.css")
    return original_page(paths, css, body, theme="default", background=illustration, width=2400 if ranklist else 1920)


def _score_ranklist_panel(paths: PluginPaths, data: dict[str, Any] | None, selected_rank: str | None) -> str:
    if not isinstance(data, dict):
        return ""
    users = data.get("users") if isinstance(data.get("users"), list) else []
    total = _as_int(data.get("totDataNum"))
    user_rank = _as_int(data.get("userRank"))
    selected = selected_rank or str(data.get("selected") or "IN")
    rows = "".join(_score_ranklist_user(paths, item if isinstance(item, dict) else {}, user_rank) for item in users[:10])
    if not rows:
        rows = '<div class="rankUser"><div class="rankUserInfo"><div class="rankUserName"><p>No rank data</p></div></div></div>'
    return f"""
<div class="ranklist">
  <div class="Player_Info"><p>RANK_LIST</p></div>
  <div class="selected"><p>{user_rank} / {total}</p><p>Selected >> {_esc(selected)}</p></div>
  {rows}
</div>"""


def _score_ranklist_user(paths: PluginPaths, item: dict[str, Any], user_rank: int) -> str:
    gameuser = item.get("gameuser") if isinstance(item.get("gameuser"), dict) else {}
    record = item.get("record") if isinstance(item.get("record"), dict) else {}
    challenge = _as_int(gameuser.get("challengeModeRank"))
    challenge_mode = max(0, challenge // 100)
    challenge_rank = challenge % 100
    avatar = str(gameuser.get("avatar") or "Introduction")
    avatar_uri = asset_uri(paths, f"html/avatar/{avatar}.png") or asset_uri(paths, "html/avatar/Introduction.png")
    challenge_uri = asset_uri(paths, f"html/otherimg/{challenge_mode}.png")
    rating = _score_ranklist_rating(record)
    index = _as_int(item.get("index"))
    return f"""
<div class="rankUser{' rankUserMe' if index == user_rank else ''}">
  <div class="ranking"><p>#{index}</p><p>{_esc(_score_ranklist_date(record.get("updated_at")))}</p></div>
  <div class="rankUserAvatar"><img src="{avatar_uri}" alt="{_esc(avatar)}"></div>
  <div class="rankUserInfo">
    <div class="rankUserName"><p name="pvis">{_esc(gameuser.get("PlayerId") or gameuser.get("name") or "UNKNOWN")}</p></div>
    <div class="rankUserRks"><p>{_as_number(gameuser.get("rankingScore")):.4f}</p></div>
    <div class="rankUserClg"><div class="Challenge"><img src="{challenge_uri}" alt="{challenge_mode}"><span>{challenge_rank}</span></div></div>
  </div>
  <div class="rankUserScore"><div class="rankUserScoreAcc"><p>{_as_number(record.get("acc")):.4f}%</p></div><div class="rankUserScoreValue"><p>{_as_int(record.get("score"))}</p></div></div>
  <div class="rankUserScoreRating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div>
</div>"""


def _score_ranklist_rating(record: dict[str, Any]) -> str:
    if record.get("Rating"):
        return _rating_asset(str(record.get("Rating")))
    score = _as_int(record.get("score"))
    fc = bool(record.get("fc"))
    if score >= 1_000_000:
        return "phi"
    if fc:
        return "FC"
    if score >= 960_000:
        return "V"
    if score >= 920_000:
        return "S"
    if score >= 880_000:
        return "A"
    if score >= 820_000:
        return "B"
    if score >= 700_000:
        return "C"
    if score > 0:
        return "F"
    return "NEW"


def _score_ranklist_date(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            return ""
    return str(value)


def ranking_list_html(paths: PluginPaths, data: dict[str, Any], catalog: SongCatalog | None = None) -> str:
    users = data.get("users") if isinstance(data.get("users"), list) else []
    me = data.get("me") if isinstance(data.get("me"), dict) else {}
    me_line = _ranking_large_line(paths, me, catalog)
    user_lines = [
        _ranking_small_line(paths, item if isinstance(item, dict) else {}, fallback_index=index + 1, catalog=catalog)
        for index, item in enumerate(users[:5])
    ]
    while len(user_lines) < 5:
        user_lines.append({"playerId": "无效用户", "index": len(user_lines) + 1})
    background = str(me_line.get("backgroundurl") or _random_background(paths))

    user_html = "".join(_ranking_user_html(paths, user) for user in user_lines)
    body = f"""
<style>
:root {{
  --phi-viewport-width: 2048px;
  --phi-viewport-height: 1080px;
}}
html, body {{
  width: 2048px !important;
  min-width: 2048px !important;
  max-width: 2048px !important;
  height: 1080px !important;
  min-height: 1080px !important;
  max-height: 1080px !important;
  overflow: hidden !important;
}}
body {{
  display: block !important;
}}
.background img {{
  filter: none !important;
  transform: none !important;
}}
</style>
<div class="background">
  <img src="{_esc(background)}" alt="background">
</div>
<div class="list">
  <div class="list_bkg"></div>
  {user_html}
</div>
<div class="info">
  <div class="txt_box">
    <p>Updated at:</p>
    <p>{_esc(me_line.get("updated", ""))}</p>
  </div>
  <div class="player_profile_box">
    <p name="pvis">{_esc(me_line.get("selfIntro") or "个人简介被胡桃吃掉惹...")}</p>
  </div>
  <div class="rks_line">
    <div class="svg-box">
      {_update_graph_inner(me_line.get("rks_history", []), me_line.get("rks_range", [0.0, 0.0]), me_line.get("rks_date", ["", ""]))}
    </div>
  </div>
  <div class="clg_info"><p>ChallengeMode History</p></div>
  <div class="clg_list_box">
    <div class="clg_line"></div>
    <div class="clg_list">
      {''.join(_ranking_challenge_history(paths, item) for item in me_line.get("clg_list", []))}
    </div>
  </div>
  <div class="b30list">
    {''.join(_ranking_b30_group(paths, group) for group in me_line.get("b30list", []))}
  </div>
  <div class="createdbox">
    <div class="phi-plugin"><p>AstrBot Phi Plugin</p></div>
    <div class="ver"><p>HTML</p></div>
  </div>
</div>
"""
    return original_page(paths, "rankingList/rankingList.css", body, theme="default", background=background, width=2048)


def chap_html(paths: PluginPaths, summary: Any, *, snapshot: SaveSnapshot) -> str:
    gameuser = _gameuser(snapshot)
    records = summary.top_records if getattr(summary, "top_records", None) else []
    counts = getattr(summary, "rating_counts", {}) or {}
    rank_counts = getattr(summary, "rank_counts", {}) or {}
    progress = {
        rank: _percentage(getattr(rank_counts.get(rank), "played", 0), getattr(rank_counts.get(rank), "total", 0))
        for rank in LEVELS
    }
    count_html = [f'<p>tot: {getattr(summary, "played_charts", 0)}/{getattr(summary, "total_charts", 0)}</p>']
    for rating in ("phi", "FC", "V", "S", "A", "B", "C", "F", "NEW"):
        value = int(counts.get(rating, 0))
        if value:
            count_html.append(f'<img src="{asset_uri(paths, f"html/otherimg/{_rating_asset(rating)}.png")}" alt="{_esc(rating)}"><p>{value}</p>')
    song_cards = "".join(_chap_song_card(paths, record, index) for index, record in enumerate(records[:30]))
    if not song_cards:
        song_cards = '<div class="song song_1"><div class="info"><div class="rank EZ"><div class="dif">NO DATA</div></div></div></div>'
    progress_html = "".join(
        f'<div class="progress {rank}-bar"><div class="progress-bar" style="width:{value:.4f}%;"></div><p>&ensp;{value:.4f}%</p></div>'
        for rank, value in progress.items()
    )
    body = f"""
<div class="illustration"><img src="{_random_background_for_records(paths, records)}" alt="chapter"></div>
<div class="bar">
  <div class="player"><p>Player: {_esc(gameuser['PlayerId'])}</p><p>chap: {_esc(getattr(summary, "name", "UNKNOWN"))}</p></div>
  <div class="count">{''.join(count_html)}</div>
  <div class="song-box" style="width: 1500px;">{song_cards}</div>
  {progress_html}
  <div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
</div>
"""
    return original_page(paths, "chap/chap.css", body, theme="default", background=_random_background_for_records(paths, records), width=2048)


def achievement_html(paths: PluginPaths, rows: list[Any], *, title: str) -> str:
    cards = []
    for row in rows:
        rating = _rating_asset(getattr(row, "min_rating", "NEW"))
        cards.append(
            '<div class="line">'
            f'<div class="song_name"><div class="num"><span name="pvis">{getattr(row, "difficulty", 0):.1f}</span></div><div class="song"><span name="pvis">{_esc(title)}</span></div><div class="dif IN"><span name="pvis">{getattr(row, "played", 0)}/{getattr(row, "total", 0)}</span></div></div>'
            f'<div class="ill_box"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div>'
            '<div class="info_box"><div class="down">'
            f'<div class="acc"><div class="box-content">{getattr(row, "avg_acc", 0):.4f}%</div><div class="suggest">FC {getattr(row, "fc_count", 0)} / Phi {getattr(row, "phi_count", 0)}</div></div>'
            f'<div class="score_rating"><div class="score">{getattr(row, "min_score", 0):,}</div><div class="rating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div></div>'
            '</div></div></div>'
        )
    body = f'<div class="head_title"><p>{_esc(title)}</p></div><div class="list_box">{"".join(cards) or _notice_line("没有找到对应定数成绩。")}</div><div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>'
    return original_page(paths, "list/list.css", body, theme="default", background=_random_background(paths))


def history_b30_html(paths: PluginPaths, changes: list[Any], snapshot: SaveSnapshot | None = None) -> str:
    gameuser = _gameuser(snapshot) if snapshot is not None else {
        "avatar": "Introduction",
        "PlayerId": "UNKNOWN",
        "rks": 0.0,
        "ChallengeMode": 0,
        "ChallengeModeRank": 0,
        "data": "0KiB",
    }
    body = [_b30_title(paths, gameuser, _level_stats([]), format_datetime(datetime.now()), ["History B30"])]
    body.append('<div class="descTip"><p>*B30变化仅以当前定数为准，实际历史定数敬请期待</p></div>')
    body.append('<div class="main-box">')
    colors = ["#00aaff", "#00f044", "#f0d000", "#ff6161", "#9c9cff"]
    for index, change in enumerate(changes):
        body.append(f'<div class="row" style="--row-color:{colors[index % len(colors)]}"><div class="date-box"><div class="upLine"></div><div class="midCirc"><div class="circInner"></div></div><div class="downLine"></div></div><div class="songs-box"><div class="row-date"><p>{_esc(change.date)}</p><div class="underLine"></div></div>')
        for song in _history_change_songs(paths, change):
            body.append(song)
        body.append("</div></div>")
    if not changes:
        body.append('<div class="row"><div class="songs-box"><div class="row-date"><p>NO HISTORY</p><div class="underLine"></div></div></div></div>')
    body.append("</div>")
    body.append('<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>')
    records = [record for change in changes for _, record in getattr(change, "new_b27", [])]
    return original_page(paths, "historyB30/historyB30.css", "\n".join(body), theme="default", background=_random_background_for_records(paths, records))


def history_summary_html(paths: PluginPaths, summary: Any) -> str:
    def pair(pair_value: tuple[str, Any] | None, digits: int = 4) -> tuple[str, str]:
        if not pair_value:
            return "--", "--"
        day, delta = pair_value
        if isinstance(delta, float):
            return str(day), f"{delta:+.{digits}f}"
        return str(day), f"{int(delta):+d}"

    rks_up_day, rks_up_delta = pair(getattr(summary, "rks_max_up", None))
    rks_down_day, rks_down_delta = pair(getattr(summary, "rks_max_down", None))
    data_up_day, data_up_delta = pair(getattr(summary, "data_max_up", None), 0)
    data_down_day, data_down_delta = pair(getattr(summary, "data_max_down", None), 0)
    body = f"""
<div id="container" class="page">
  <header class="header"><div class="title"><div class="title-main">存档历史分析</div><div class="title-sub">统计范围为绑定至今</div></div><div class="meta"><div class="meta-item"><span class="meta-k">生成时间</span><span class="meta-v">{_esc(format_datetime(datetime.now()))}</span></div></div></header>
  <section class="grid grid-3">
    {_history_card("查分天数", getattr(summary, "total_days", 0), "发生过 score / rks / data / challenge 任一事件的天数")}
    {_history_card("更新次数", getattr(summary, "total_updates", 0), "按所有事件时间戳去重统计")}
    <div class="card"><div class="card-h">RKS 最大波动</div>{_history_split("UP", rks_up_day, rks_up_delta, "up")}{_history_split("DOWN", rks_down_day, rks_down_delta, "down")}<div class="card-s">按天累计增量</div></div>
  </section>
  <section class="grid grid-2">
    {_history_rank_card("打得最多的曲目", getattr(summary, "most_played", []))}
    {_history_card("总新纪录", getattr(summary, "total_score_records", 0), "历史成绩记录总数")}
  </section>
  <section class="grid grid-3">
    {_history_rank_card("新纪录最多", getattr(summary, "most_new_records", []))}
    <div class="card"><div class="card-h">Data 最大波动</div>{_history_split("UP", data_up_day, data_up_delta, "up")}{_history_split("DOWN", data_down_day, data_down_delta, "down")}<div class="card-s">按天累计字节变化</div></div>
    {_history_rank_card("推分最晚", getattr(summary, "latest_push_times", []))}
  </section>
  <section class="grid">{_history_rank_card("AP 最多", getattr(summary, "most_ap_days", []))}</section>
  <footer class="footer"><div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div></footer>
</div>
"""
    return original_page(paths, "analyzeSaveHistory/analyzeSaveHistory.css", body, theme="default", background=_random_background(paths))


def rand_html(paths: PluginPaths, song: Song, *, chart_rank: str | None = None) -> str:
    chart = song.charts.get(chart_rank or "") if chart_rank else next(iter(song.display_charts()), None)
    illustration = _song_illustration(paths, song)
    body = f"""
<div class="ill"><img src="{illustration}" alt="曲绘"></div>
<div class="box">
  <div class="box-left"><div class="name-box"><div class="name-left"><p1>{_esc(song.title)}</p1><p2>{_esc(song.composer)}</p2></div></div><div class="info-box"><div class="info-left"><div class="part"><p1>Chart</p1><p2>{_esc(chart.charter if chart else "")}</p2></div><div class="part"><p1>Illustration</p1><p2>{_esc(song.illustrator)}</p2></div></div></div></div>
  <div class="box-mid"><div class="mid-up"></div><div class="mid-down"></div></div>
  <div class="box-right"><div class="name-box"><div class="right-up"></div><div class="leave"><div class="leave-diff"><p>{_esc((chart.difficulty_text if chart else "") or (f"{chart.difficulty:.1f}" if chart and chart.difficulty else "?"))}</p></div><div class="leave-rank"><p>{_esc(chart.rank if chart else "?")}</p></div></div><div class="name-right"></div></div><div class="info-box"><div class="info-mid"></div><div class="info-right"></div></div></div>
</div>
"""
    return original_page(paths, "rand/rand.css", body, theme="default", background=illustration)


def randclg_html(paths: PluginPaths, target: int, charts: list[ChartEntry]) -> str:
    songs = "".join(_randclg_song_card(paths, chart, index) for index, chart in enumerate(charts))
    body = f"""
<div class="box">{songs}</div>
<div class="tot-box"><img src="{asset_uri(paths, "html/otherimg/5.png")}" alt="Challenge"><div class="tot_clg"><p>{target}</p></div></div>
<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
"""
    return original_page(paths, "clg/clg.css", body, theme="default", background=_random_background_for_charts(paths, charts))


def song_html(paths: PluginPaths, song: Song, *, comments: dict[str, Any] | None = None) -> str:
    illustration = _song_illustration(paths, song)
    charts = "".join(_atlas_chart_row(chart) for chart in song.display_charts())
    note_totals = "".join(f"<p>{chart.combo or '-'}</p>" for chart in song.display_charts())
    comment_html = _atlas_comment_box(paths, comments)
    body = f"""
<div class="big-box">
  <div class="box">
    <div class="info-box">
      <div class="name-box clip-box"><div class="song"><p name="pvis">{_esc(song.title)}</p></div><div class="composer"><p name="pvis">{_esc(song.composer)}</p></div></div>
      <div class="charts-box"><div class="length"><p name="pvis">{_esc(song.length)}</p></div><div class="txt"><div class="sqrt"><p>SONG'S_INFO</p></div><div class="line"><p name="pvis">{_safe(song.sp_info.replace(chr(10), '<br>'))}</p></div></div><div class="chart">{charts}<div class="note-box"><p>Total</p>{note_totals}</div></div></div>
    </div>
    <div class="ill-box clip-box"><img src="{illustration}" alt="曲绘"></div>
    {'<div class="original-tag"><p>Phigros Original</p></div>' if song.is_original else ''}
  </div>
  <div class="other-info">{_atlas_info("BPM", song.bpm)}{_atlas_info("Illustrator", song.illustrator)}{_atlas_info("Chapter", song.chapter)}</div>
</div>
{comment_html}
<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
"""
    return original_page(paths, "atlas/atlas.css", body, theme="default", background=illustration)


def chart_html(
    paths: PluginPaths,
    song: Song,
    rank: str,
    *,
    tags: dict[str, Any] | None = None,
    user_tags: list[str] | None = None,
    chart_preview: str = "",
) -> str:
    chart = song.charts.get(rank)
    if chart is None:
        raise ValueError(f"{song.title} does not have {rank} chart")
    note_info = _chart_note_info(paths, song.id, rank, chart.combo)
    tag_items = _chart_tag_items(tags or {}, user_tags or [])
    tag_max = max([item["value"] for item in tag_items], default=1)
    illustration = _song_illustration(paths, song)
    distribution = "".join(_chart_distribution_bar(row) for row in note_info["distribution"])
    tag_rows = "".join(_chart_tag_row(item, tag_max) for item in tag_items) or '<div class="tag-row empty"><p>No online tags</p></div>'
    preview_html = ""
    if chart_preview:
        preview_html = f"""
<div class="backBlock">
  <div class="totalBox" id="box">
    <img src="{chart_preview}" alt="chart preview">
  </div>
</div>"""
    body = f"""
{preview_html}
<div class="info-box chart-panel">
  <div class="basic-box">
    <div class="ill-box">
      <div class="box-title"><p>Illustration</p></div>
      <div class="box-content dot-box">
        {_dot_box()}
        <img src="{illustration}" alt="{_esc(song.title)}">
      </div>
    </div>
    <div class="basic-info">
      <div class="box-title"><p>Basic Information</p></div>
      <div class="box-content dot-box">
        {_dot_box()}
        <div class="info-content">
          {_chart_content_item("曲目", song.title)}
          {_chart_content_item("曲目时长", song.length or "-")}
          {_chart_content_item("难度", f"{rank} {_chart_difficulty_text(chart)}")}
          {_chart_content_item("谱师", chart.charter or "-")}
        </div>
      </div>
    </div>
  </div>
  <div class="chart-info">
    <div class="box-title"><p>Chart Information</p></div>
    <div class="box-content dot-box">
      {_dot_box()}
      <div class="info-content chart-info-content">
        <div class="notes-box">
          <div class="content-title"><p>Notes</p></div>
          <div class="content">
            {_chart_note_count("tap-p", note_info["tap"], "Tap")}
            {_chart_note_count("drag-p", note_info["drag"], "Drag")}
            {_chart_note_count("hold-p", note_info["hold"], "Hold")}
            {_chart_note_count("flick-p", note_info["flick"], "Flick")}
            {_chart_note_count("", note_info["combo"], "Combo")}
          </div>
        </div>
        <div class="words-box">
          <div class="content-title"><p>Chart Tag</p></div>
          <div class="box-tip"><p>{'API' if tag_items else 'No data'}</p></div>
          <div class="words chart-tags">{tag_rows}</div>
        </div>
        <div class="notes-bar">
          <div class="content-title"><p>Notes Distribution</p></div>
          <div class="box-tip"><p>谱面时长：{_esc(note_info["chart_length"])}</p></div>
          <div class="bar-box" id="bar-box">{distribution}</div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
"""
    return original_page(
        paths,
        ("chartInfo/chartInfo.css", "chartImg/chartImg.css"),
        body,
        theme="default",
        background=illustration,
        width=1200,
    )


def ill_html(paths: PluginPaths, illustration: str, illustrator: str = "") -> str:
    body = f"""
<img src="{illustration}" alt="曲绘">
<div class="info-box">
  <div class="phi"><img src="{asset_uri(paths, "html/otherimg/title.png")}" alt="Phigros"></div>
  <div class="line"></div>
  <div class="info">
    <div class="up"><p>Illustrator</p></div>
    <div class="down"><p>{_esc(illustrator or "Unknown")}</p></div>
  </div>
</div>"""
    return original_page(paths, "ill/ill.css", body, theme="default", background=illustration)


def guess_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    width = _as_int(data.get("width")) or 120
    height = _as_int(data.get("height")) or 120
    x = _as_int(data.get("x"))
    y = _as_int(data.get("y"))
    style = bool(data.get("style"))
    viewport_width = 2048 if style else width
    viewport_height = 1080 if style else height
    illustration = str(data.get("illustration") or "")
    ans = str(data.get("ans") or "")
    filter_style = str(data.get("filterStyle") or "")
    body = f"""
<style>
:root {{
  --phi-viewport-width: {viewport_width}px;
  --phi-viewport-height: {viewport_height}px;
}}
html, body {{
  width: {viewport_width}px !important;
  min-width: {viewport_width}px !important;
  max-width: {viewport_width}px !important;
  height: {viewport_height}px !important;
  min-height: {viewport_height}px !important;
  max-height: {viewport_height}px !important;
  background: #000 !important;
  overflow: hidden !important;
}}
.background {{
  display: none !important;
}}
</style>
<svg width="0" height="0" style="position:absolute">
  <filter id="phiLineArt">
    <feColorMatrix type="saturate" values="0" in="SourceGraphic" result="gray" />
    <feComponentTransfer in="gray">
      <feFuncR type="linear" slope="-1" intercept="1" />
      <feFuncG type="linear" slope="-1" intercept="1" />
      <feFuncB type="linear" slope="-1" intercept="1" />
    </feComponentTransfer>
    <feGaussianBlur stdDeviation="1" result="blur" />
    <feBlend mode="color-dodge" in="blur" in2="gray" result="sketch" />
    <feComponentTransfer in="sketch">
      <feFuncR type="linear" slope="3" intercept="-2" />
      <feFuncG type="linear" slope="3" intercept="-2" />
      <feFuncB type="linear" slope="3" intercept="-2" />
    </feComponentTransfer>
  </filter>
</svg>
{f'<div class="ans"><img src="{_esc(ans)}" alt="答案"></div>' if ans else ''}
"""
    if style:
        body += f"""
<div class="img"
  style="width: {width}px;height: {height}px;margin-left: {x}px;margin-top: {y}px;border: 1px solid #888;filter: drop-shadow(0 0 5px #fff);">
  <img src="{_esc(illustration)}" alt="曲绘" style="margin-left: -{x}px;margin-top: -{y}px;{filter_style}">
</div>
"""
    else:
        body += f"""
<div class="img" style="width: {width}px;height: {height}px;">
  <img src="{_esc(illustration)}" alt="曲绘" style="margin-left: -{x}px;margin-top: -{y}px;{filter_style}">
</div>
"""
    return original_page(paths, "guess/guess.css", body, theme="default", background="", width=viewport_width)


def notice_html(paths: PluginPaths, notice: dict[str, Any]) -> str:
    notices = _notice_items(notice)
    if not notices:
        body = """
<main class="notice-page">
  <article class="notice-card empty">
    <h1 class="notice-title">暂无公告</h1>
  </article>
</main>"""
        return original_page(paths, "newnotice/newnotice.css", body, theme="default", background=_random_background(paths))

    cards: list[str] = ['<main class="notice-page">']
    for item in notices:
        title = _esc(item.get("title") or "公告")
        date = _notice_date_text(item.get("date") or item.get("time") or item.get("createdAt"))
        lines = _notice_content_lines(item.get("content"))
        image = image_data_uri(paths, str(item.get("image") or "")) if item.get("image") else ""
        cards.append('<article class="notice-card">')
        cards.append(f'<h1 class="notice-title">{title}</h1>')
        if date:
            cards.append(f'<div class="notice-date">{_esc(date)}</div>')
        cards.append('<section class="notice-content">')
        for line in lines:
            if not line.strip():
                cards.append('<div class="notice-space"></div>')
            elif line.strip().startswith("#"):
                cards.append(f'<p class="notice-tags">{_esc(line)}</p>')
            else:
                cards.append(f"<p>{_esc(line)}</p>")
        cards.append("</section>")
        if image:
            cards.append(f'<img class="notice-image" src="{image}" alt="{title}">')
        cards.append("</article>")
    cards.append("</main>")
    return original_page(paths, "newnotice/newnotice.css", "\n".join(cards), theme="default", background=_random_background(paths))


def newlog_html(
    paths: PluginPaths,
    log: VersionLog | None,
    *,
    catalog: SongCatalog | None = None,
    update_logs: list[dict[str, Any]] | None = None,
) -> str:
    rows = _newlog_rows(paths, log, catalog=catalog, update_logs=update_logs or [])

    body = ["<table border=\"1\"><tbody>"]
    for row in rows:
        body.append("<tr>")
        for cell in row:
            if cell.get("col") == 0 or cell.get("row") == 0:
                continue
            tag = "th" if int(cell.get("col") or 0) == 4 else "td"
            colspan = f' colspan="{int(cell["col"])}"' if cell.get("col") else ""
            rowspan = f' rowspan="{int(cell["row"])}"' if cell.get("row") else ""
            styles = []
            if cell.get("bkg"):
                styles.append(f"background-color: {cell['bkg']}")
            if cell.get("color"):
                styles.append(f"color: {cell['color']}")
            style = f' style="{"; ".join(styles)}"' if styles else ""
            body.append(f"<{tag}{colspan}{rowspan}{style}>{_esc(cell.get('cnt', ''))}</{tag}>")
        body.append("</tr>")
    body.append("</tbody></table>")
    return original_page(paths, "newSong/newSong.css", "\n".join(body), theme="default", background=_random_background(paths))


def _newlog_rows(
    paths: PluginPaths,
    log: VersionLog | None,
    *,
    catalog: SongCatalog | None,
    update_logs: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    if log is None:
        return [[{"cnt": "\u6682\u65e0\u672c\u5730\u7248\u672c\u66f4\u65b0\u65e5\u5fd7", "col": 4, "bkg": "#222", "color": "#fff"}]]

    rows: list[list[dict[str, Any]]] = [
        [{"cnt": "\u65b0\u66f2\u901f\u9012", "col": 4, "bkg": "#222", "color": "#fff"}],
        [{"cnt": "\u66f2\u540d"}, {"cnt": "\u96be\u5ea6"}, {"cnt": "\u5b9a\u6570"}, {"cnt": "\u7269\u91cf"}],
    ]
    new_songs = _newlog_new_songs(log, catalog, update_logs)
    if new_songs:
        for song in new_songs:
            for chart in song.display_charts():
                if chart.rank not in LEVELS:
                    continue
                bkg = _newlog_level_color(chart.rank)
                rows.append([
                    {"cnt": song.title},
                    {"cnt": chart.rank, "bkg": bkg},
                    {"cnt": _newlog_chart_difficulty(chart), "bkg": bkg},
                    {"cnt": chart.combo or "", "bkg": bkg},
                ])
    else:
        rows.append([{"cnt": "\u6682\u672a\u4ece\u66f4\u65b0\u65e5\u5fd7\u4e2d\u5339\u914d\u5230\u65b0\u66f2", "col": 4, "bkg": "#ffffffcc", "color": "#111"}])

    rows.extend([
        [{"cnt": "\u5b9a\u6570&\u8c31\u9762\u4fee\u6539", "col": 4, "bkg": "#222", "color": "#fff"}],
        [{"cnt": "\u66f2\u540d"}, {"cnt": "\u96be\u5ea6"}, {"cnt": "\u6761\u76ee"}, {"cnt": "\u60c5\u51b5"}],
    ])
    changed_rows = _newlog_changed_rows(paths, catalog)
    if changed_rows:
        rows.extend(changed_rows)
    else:
        rows.append([{"cnt": "\u6682\u672a\u68c0\u6d4b\u5230\u672c\u5730\u5b9a\u6570/\u7269\u91cf\u4fee\u6539", "col": 4, "bkg": "#ffffffcc", "color": "#111"}])
    return _newlog_apply_rowspan(rows)


def _newlog_new_songs(
    log: VersionLog,
    catalog: SongCatalog | None,
    update_logs: list[dict[str, Any]],
) -> list[Song]:
    if catalog is None:
        return []
    update_text = "\n".join(_newlog_update_texts(log, update_logs))
    update_key = _newlog_text_key(update_text)
    result: list[Song] = []
    for song in catalog.all_songs():
        candidates = [song.title, song.id, *song.aliases]
        for candidate in candidates:
            key = _newlog_text_key(candidate)
            if _newlog_matchable_key(key) and key in update_key:
                result.append(song)
                break
    return result


def _newlog_update_texts(log: VersionLog, update_logs: list[dict[str, Any]]) -> list[str]:
    texts = [log.version_label, log.whatsnew]
    for item in update_logs:
        texts.extend([
            str(item.get("version") or ""),
            _strip_inline_html(str(item.get("rawHtml") or "")),
        ])
    return [text for text in texts if text]


def _newlog_changed_rows(paths: PluginPaths, catalog: SongCatalog | None) -> list[list[dict[str, Any]]]:
    if catalog is None:
        return []
    previous = _newlog_previous_difficulty(paths)
    if not previous:
        return []
    current_notes = _newlog_load_notes(paths.info / "notesInfo.json")
    old_notes = _newlog_load_notes(paths.info / "oldNotesInfo.json")
    rows: list[list[dict[str, Any]]] = []
    for song in catalog.all_songs():
        old_row = previous.get(song.id)
        if old_row is None:
            continue
        for chart in song.display_charts():
            if chart.rank not in LEVELS:
                continue
            old_difficulty = _newlog_number(old_row.get(chart.rank))
            new_difficulty = chart.difficulty
            bkg = _newlog_level_color(chart.rank)
            current_counts = _newlog_note_counts(current_notes, song.id, chart.rank)
            old_counts = _newlog_note_counts(old_notes, song.id, chart.rank)
            if old_difficulty is None:
                for label, value in _newlog_new_chart_items(new_difficulty, current_counts, chart.combo):
                    rows.append([
                        {"cnt": song.title},
                        {"cnt": chart.rank, "bkg": bkg},
                        {"cnt": label, "bkg": bkg},
                        {"cnt": value, "bkg": bkg},
                    ])
                continue
            if old_difficulty is not None and new_difficulty is not None and abs(old_difficulty - new_difficulty) > 0.0001:
                incr = old_difficulty < new_difficulty
                rows.append([
                    {"cnt": song.title},
                    {"cnt": chart.rank, "bkg": bkg},
                    {"cnt": "\u5b9a\u6570", "bkg": bkg},
                    {
                        "cnt": f"{old_difficulty:g} ({'+' if incr else '-'}) {new_difficulty:g}",
                        "color": "red" if incr else "green",
                        "bkg": bkg,
                    },
                ])
            if old_counts is not None and current_counts is not None:
                for index, label in enumerate(("tap", "drag", "hold", "flick")):
                    if old_counts[index] != current_counts[index]:
                        rows.append(_newlog_delta_row(song.title, chart.rank, bkg, label, old_counts[index], current_counts[index]))
                old_combo = sum(old_counts)
                current_combo = sum(current_counts)
                if old_combo != current_combo:
                    rows.append(_newlog_delta_row(song.title, chart.rank, bkg, "combo", old_combo, current_combo))
    return rows


def _newlog_delta_row(song_title: str, rank: str, bkg: str, label: str, old_value: int, new_value: int) -> list[dict[str, Any]]:
    incr = old_value < new_value
    return [
        {"cnt": song_title},
        {"cnt": rank, "bkg": bkg},
        {"cnt": label, "bkg": bkg},
        {
            "cnt": f"{old_value} ({'+' if incr else '-'}) {new_value}",
            "color": "red" if incr else "green",
            "bkg": bkg,
        },
    ]


def _newlog_new_chart_items(
    difficulty: float | None,
    counts: tuple[int, int, int, int] | None,
    combo: int | None,
) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if counts is not None:
        items.extend(zip(("tap", "drag", "hold", "flick"), counts, strict=True))
    if difficulty is not None:
        items.append(("\u5b9a\u6570", f"{difficulty:g}"))
    total = sum(counts) if counts is not None else combo
    if total:
        items.append(("combo", total))
    return items


def _newlog_load_notes(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _newlog_note_counts(notes: dict[str, Any], song_id: str, rank: str) -> tuple[int, int, int, int] | None:
    song_notes = notes.get(song_id.removesuffix(".0")) or notes.get(song_id)
    if not isinstance(song_notes, dict):
        return None
    chart_notes = song_notes.get(rank)
    if not isinstance(chart_notes, dict):
        return None
    totals = chart_notes.get("t")
    if not isinstance(totals, list) or len(totals) < 4:
        return None
    result: list[int] = []
    for value in totals[:4]:
        parsed = _newlog_number(value)
        if parsed is None:
            return None
        result.append(int(parsed))
    return (result[0], result[1], result[2], result[3])


def _newlog_previous_difficulty(paths: PluginPaths) -> dict[str, dict[str, str]]:
    old_info = paths.info / "oldInfo"
    versions = sorted(int(path.name) for path in old_info.iterdir() if path.is_dir() and path.name.isdigit()) if old_info.exists() else []
    if len(versions) < 2:
        return {}
    path = old_info / str(versions[-2]) / "change.csv"
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            song_id = str(row.get("id") or "").strip()
            if song_id:
                rows[song_id] = {str(key): str(value or "") for key, value in row.items()}
    return rows


def _newlog_apply_rowspan(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    for i, row in enumerate(rows):
        if not row or "col" in row[0] or len(row) != 4:
            continue
        if row[0].get("cnt") == "\u66f2\u540d" or row[0].get("row") == 0:
            continue
        k = i + 1
        while k < len(rows) and len(rows[k]) == 4 and rows[k][0].get("cnt") == row[0].get("cnt") and "col" not in rows[k][0]:
            rows[k][0]["row"] = 0
            k += 1
        if k > i + 1:
            row[0]["row"] = k - i
    return rows


def _newlog_level_color(rank: str) -> str:
    return {
        "EZ": "#6fe4a7",
        "HD": "#75c7ff",
        "IN": "#ff8fb8",
        "AT": "#f2a7ff",
    }.get(rank, "#ffffffcc")


def _newlog_chart_difficulty(chart: Any) -> str:
    if getattr(chart, "difficulty", None) is not None:
        return f"{float(chart.difficulty):g}"
    return str(getattr(chart, "difficulty_text", "") or "")


def _newlog_number(value: Any) -> float | None:
    try:
        text = str(value).strip()
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def _newlog_text_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value).casefold())


def _newlog_matchable_key(value: str) -> bool:
    if len(value) >= 3:
        return True
    return len(value) >= 2 and any(ord(char) > 127 for char in value)


def _strip_inline_html(value: str) -> str:
    text = value.replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")
    text = re.sub(r"</?div[^>]*>", "\n", text)
    return re.sub(r"<[^>]+>", "", text)

def update_html(paths: PluginPaths, summary: UpdateProgressSummary, *, history: dict[str, Any] | None = None) -> str:
    gameuser = {
        "PlayerId": summary.player_id or summary.player_name or "UNKNOWN",
        "rks": summary.ranking_score,
        "ChallengeMode": max(0, min(5, _as_int(summary.challenge_mode_rank) // 100)),
        "ChallengeModeRank": _as_int(summary.challenge_mode_rank) % 100,
    }
    added_rks_notes = [
        _signed_delta(summary.rks_delta, digits=4),
        _signed_delta(summary.data_delta, suffix="KiB"),
    ]
    box_line = _update_box_lines(paths, summary.recent_days)
    rks_history, rks_range, rks_date = _series_lines(history or {}, "rks", current=(summary.modified_at, summary.ranking_score), money=False)
    challenge_img = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    task_data = []
    if summary.is_first_record:
        task_data.append({
            "song": "首次记录",
            "illustration": asset_uri(paths, "html/otherimg/data.png"),
            "request": {"rank": "INFO", "value": "首次记录"},
            "reward": 0,
            "finished": True,
        })
    body = f"""
    <div class="title">
        <div class="r">
            <p>Player: {_esc(gameuser['PlayerId'])}</p>
            <p>RankingScore: {summary.ranking_score:.4f}{_delta_span(added_rks_notes[0])}</p>
            <div class="Challenge">
                <p>ChallengeMode:</p>
                <div class="Challenge-r">
                    <img src="{challenge_img}" alt="Challenge">
                    <p>{gameuser['ChallengeModeRank']}</p>
                </div>
            </div>
            <p>Notes: {_format_money(summary.data_money)}{_delta_span(added_rks_notes[1])}</p>
            <p>Date: {_esc(summary.modified_at)}</p>
        </div>
        <div class="rks_line">
            <div class="svg-box">
                {_update_graph_inner(rks_history, rks_range, rks_date)}
            </div>
        </div>
    </div>
    {_update_record_box_html(box_line)}
    <div class="createdbox">
        <div class="phi-plugin"><p>AstrBot Phi Plugin</p></div>
        <div class="ver"><p>HTML</p></div>
    </div>
    """
    # keep the original layout scaffolding but populate it with the real update data
    return original_page(paths, "update/update.css", body, theme="default", background=_random_background(paths), width=800)


def jrrp_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    sentence = data.get("sentence") if isinstance(data.get("sentence"), dict) else {}
    good = [str(item) for item in data.get("good", [])][:4]
    bad = [str(item) for item in data.get("bad", [])][:4]
    body = f"""
<style>
:root {{
  --phi-viewport-width: 2048px;
  --phi-viewport-height: 1080px;
}}
html, body {{
  height: 1080px !important;
  min-height: 1080px !important;
  max-height: 1080px !important;
}}
.background {{
  display: none !important;
}}
</style>
<div class="jrrpBkg">
  <img src="{_esc(str(data.get("bkg") or _random_background(paths)))}" alt="background">
</div>
<div class="upperImg">
  <img src="{asset_uri(paths, "html/jrrp/ShineAfter.removebg.png")}" alt="upper">
</div>
<div class="title"><p>——·今日运势·——</p></div>
<div class="lucky ac-{_as_int(data.get("luckRank"))}"><p>{_as_int(data.get("lucky"))}</p></div>
<div class="date">
  <div class="year"><p>{_esc(data.get("year", ""))}</p><p>YYYY</p></div>
  <div class="mounth"><p>{_esc(data.get("month", ""))}</p><p>MM</p></div>
  <div class="day"><p>{_esc(data.get("day", ""))}</p><p>DD</p></div>
</div>
<div class="left">
  <div class="afont"><p><i>宜</i></p></div>
  {"".join(f"<p>{_esc(word)}</p>" for word in good)}
</div>
<div class="right">
  <div class="afont"><p><i>忌</i></p></div>
  {"".join(f"<p>{_esc(word)}</p>" for word in bad)}
</div>
<div class="sentences"><p name="pvis">{_esc(sentence.get("hitokoto", ""))}</p></div>
<div class="from"><p name="pvis">——「{_esc(sentence.get("from", ""))}」</p></div>
"""
    return original_page(paths, "jrrp/jrrp.css", body, theme="default", background="", width=2048)


def user_setting_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    items = data.get("items") if isinstance(data.get("items"), list) else []
    groups = []
    for item in items:
        if not isinstance(item, dict):
            continue
        options_html = []
        for option in item.get("options", []):
            if not isinstance(option, dict):
                continue
            selected = " selected" if option.get("selected") else ""
            tag = '<span class="option-tag">已选中</span>' if option.get("selected") else ""
            options_html.append(
                f"""
<div class="option-card{selected}">
  <div class="option-title-line">
    <p class="option-title">{_esc(option.get("title", ""))}</p>
    {tag}
  </div>
  <p class="option-desc">{_esc(option.get("description", ""))}</p>
</div>"""
            )
        groups.append(
            f"""
<div class="setting-group">
  <div class="setting-head">
    <p class="setting-title">{_esc(item.get("title", ""))}</p>
    <p class="setting-current">当前：{_esc(item.get("currentTitle", ""))}</p>
  </div>
  <p class="setting-desc">{_esc(item.get("description", ""))}</p>
  <div class="option-row">{"".join(options_html)}</div>
</div>"""
        )
    body = f"""
<div class="page-wrap">
  <div class="panel">
    <div class="title-box">
      <p class="page-title">{_esc(data.get("pageTitle", "Phi-Plugin 用户设置"))}</p>
      <p class="page-desc">{_esc(data.get("pageDescription", ""))}</p>
    </div>
    {"".join(groups)}
  </div>
  <div class="createdbox">
    <div class="phi-plugin"><p>AstrBot Phi Plugin</p></div>
    <div class="ver"><p>HTML</p></div>
  </div>
</div>
"""
    return original_page(paths, "setting/userSetting.css", body, theme="default", background=_random_background(paths), width=1080)


def sign_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    edge_rate = data.get("edgeRate") if isinstance(data.get("edgeRate"), dict) else {}
    daily_tasks = data.get("dailyTasks") if isinstance(data.get("dailyTasks"), list) else []
    body = f"""
<style>
:root {{
  --phi-viewport-width: 2048px;
  --phi-viewport-height: 1080px;
}}
html, body {{
  height: 1080px !important;
  min-height: 1080px !important;
  max-height: 1080px !important;
}}
</style>
<div class="backGlass clip-box"></div>
<div class="dashboard">
  <div class="playerInfo leftAbsolute">
    <div class="blackBlock clip-box"></div>
    <div class="avatar clip-box"><img src="{asset_uri(paths, f"html/avatar/{_esc(str(data.get('avatar') or 'Introduction'))}.png") or asset_uri(paths, "html/avatar/Introduction.png")}" alt="avatar"></div>
    <div class="playerId"><p name="pvis">{_esc(data.get("PlayerId", "UNKNOWN"))}</p></div>
    <div class="rks clip-box"><p>{_esc(data.get("Rks", "0.0000"))}</p></div>
    <div class="clgBox"><div class="Challenge"><img src="{asset_uri(paths, f"html/otherimg/{_as_int(data.get('ChallengeMode'))}.png")}" alt="Challenge"><p>{_as_int(data.get("ChallengeModeRank"))}</p></div></div>
    <div class="date"><p>{_esc(data.get("Date", ""))}</p></div>
    <div class="dataBox clip-box"><p>{_as_int(data.get("Notes"))} Notes</p></div>
    <div class="spInfo colorful-background clip-box"><p>累计签到 {_as_int(data.get("signDays"))} 天</p></div>
  </div>
  <div class="edgeProgress clip-box leftAbsolute">
    {_sign_edge_track(edge_rate, "EZ")}
    {_sign_edge_track(edge_rate, "HD")}
    {_sign_edge_track(edge_rate, "IN")}
    {_sign_edge_track(edge_rate, "AT")}
  </div>
  <div class="leftRail leftAbsolute">
    <div class="luckCard clip-box leftAbsolute">
      <p class="cardTitle leftAbsolute">今日人品</p>
      <p class="luckValue leftAbsolute">{_as_int(data.get("lucky"))}</p>
    </div>
    <div class="keyWordsCard leftAbsolute">
      <div class="wordsBox clip-box">
        <p class="leftAbsolute">宜</p>
        {''.join(f'<p class="leftAbsolute">{_esc(word)}</p>' for word in data.get("good", [])[:4])}
      </div>
      <div class="wordsBox clip-box">
        <p class="leftAbsolute">忌</p>
        {''.join(f'<p class="leftAbsolute">{_esc(word)}</p>' for word in data.get("bad", [])[:4])}
      </div>
    </div>
    <div class="quoteCard clip-box leftAbsolute">
      <p class="cardTitle leftAbsolute">每日一言</p>
      <div class="quoteText leftAbsolute"><p name="pvis">{_esc(data.get("quote", ""))}</p></div>
    </div>
  </div>
  <div class="dailySongsPanel clip-box leftAbsolute">
    <div class="panelHeader clip-box leftAbsolute"><p>DAILY TASK SONGS</p></div>
    {''.join(_sign_daily_task(task) for task in daily_tasks[:5])}
  </div>
  <div class="noticePanel clip-box leftAbsolute">
    {_sign_notice(data.get("notice")) if data.get("notice") else _sign_calendar(data.get("calendar"))}
  </div>
  <div class="createdbox leftAbsolute">
    <div class="phi-plugin"><p>AstrBot Phi Plugin</p></div>
    <div class="ver"><p>HTML</p></div>
  </div>
</div>
"""
    return original_page(paths, "sign/sign.css", body, theme="default", background=str(data.get("background") or _random_background(paths)), width=2048)


def tasks_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    tasks = data.get("task") if isinstance(data.get("task"), list) else []
    challenge_img = asset_uri(paths, f"html/otherimg/{_as_int(data.get('ChallengeMode'))}.png")
    change_notes = str(data.get("change_notes") or "")
    body = f"""
<div class="title">
  <div class="l">
    <img src="{asset_uri(paths, "html/otherimg/Phigros_Icon_3.0.0.png")}" alt="icon">
    <div class="doc">
      <p>Phi-Plugin任务列表</p>
      <p style="font-size:20px;">{_esc(data.get("task_ans", ""))}</p>
      <p style="font-size:20px;">{_esc(data.get("task_ans1", ""))}</p>
    </div>
  </div>
  <div class="m"></div>
  <div class="r">
    <p>Player: {_esc(data.get("PlayerId", "UNKNOWN"))}</p>
    <p>RankingScore: {_esc(data.get("Rks", "0.0000"))}</p>
    <div class="Challenge"><p>ChallengeMode:</p><div class="Challenge-r"><img src="{challenge_img}" alt="Challenge"><p>{_as_int(data.get("ChallengeModeRank"))}</p></div></div>
    <p>Notes: {_as_int(data.get("Notes"))}{' <span style="color:' + ('gold' if change_notes.startswith('+') else 'red') + ';">' + _esc(change_notes) + '</span>' if change_notes else ''}</p>
    <p>Date: {_esc(data.get("Date", ""))}</p>
  </div>
</div>
<div class="box">
  {''.join(_tasks_card(task, index) for index, task in enumerate(tasks) if task)}
  {'' if any(tasks) else _tasks_empty()}
</div>
<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>
{('<div class="tips"><p>Tip:' + _esc(data.get("tips", "")) + '</p></div>') if data.get("tips") else ''}
"""
    return original_page(paths, "tasks/tasks.css", body, theme="default", background=str(data.get("background") or _random_background(paths)), width=800)


def _sign_edge_track(edge_rate: dict[str, Any], level: str) -> str:
    value = edge_rate.get(level) if isinstance(edge_rate.get(level), dict) else {}
    return f"""
<div class="edgeTrack clip-box edgeFill--{_esc(level)}">
  <div class="edgeFill edgeFill--unlock" style="--rate:{_esc(value.get("unlock", "0%"))}"></div>
  <div class="edgeFill edgeFill--fc" style="--rate:{_esc(value.get("fc", "0%"))}"></div>
  <div class="edgeFill edgeFill--phi" style="--rate:{_esc(value.get("phi", "0%"))}"></div>
</div>"""


def _sign_daily_task(task: dict[str, Any]) -> str:
    finished = bool(task.get("finished"))
    return f"""
<div class="songItem clip-box leftAbsolute {'songItem--finished' if finished else ''}">
  {'<div class="taskStatus clip-box taskStatus--finished">已完成</div>' if finished else ''}
  <div class="songCover clip-box"><img src="{_esc(task.get("illustration", ""))}" alt="{_esc(task.get("song", ""))}"></div>
  <div class="songText">
    <p class="songIndex">{_esc(task.get("index", ""))}</p>
    <p class="songName" name="pvis">{_esc(task.get("song", ""))}</p>
    <p class="songMeta">{_esc(task.get("meta", ""))}</p>
  </div>
</div>"""


def _sign_notice(notice: Any) -> str:
    if not isinstance(notice, dict):
        return ""
    content = notice.get("content") if isinstance(notice.get("content"), list) else []
    rows = []
    for index, item in enumerate(content[:5]):
        rows.append(f"""
<div class="noticeRow clip-box leftAbsolute">
  <div class="noticeRowIndex"><p><span style="color:skyblue;">{index + 1}.</span>{_esc(item)}</p></div>
</div>""")
    return f"""
<div class="panelHeader clip-box"><p>Notice Board</p></div>
<div class="noticeBody noticeNotice">
  <div class="noticeRow noticeTitleRow leftAbsolute"><p class="noticeTitle">{_esc(notice.get("title", "Notice"))}</p></div>
  {''.join(rows)}
</div>"""


def _sign_calendar(calendar: Any) -> str:
    if not isinstance(calendar, dict):
        calendar = {"title": "", "weekdays": [], "weeks": []}
    weekdays = calendar.get("weekdays") if isinstance(calendar.get("weekdays"), list) else []
    weeks = calendar.get("weeks") if isinstance(calendar.get("weeks"), list) else []
    week_rows = []
    for week in weeks:
        cells = []
        for cell in week if isinstance(week, list) else []:
            if not isinstance(cell, dict) or cell.get("empty"):
                cells.append('<div class="calendarCell empty"></div>')
                continue
            classes = ["calendarCell"]
            if cell.get("signed"):
                classes.append("signed")
            if cell.get("today"):
                classes.append("today")
            cells.append(f'<div class="{" ".join(classes)}"><span>{_as_int(cell.get("day"))}</span></div>')
        week_rows.append(f'<div class="calendarWeek clip-box leftAbsolute">{"".join(cells)}</div>')
    return f"""
<div class="panelHeader clip-box"><p>SIGN-IN CALENDAR</p></div>
<div class="noticeBody noticeCalendar">
  <div class="calendarTitle leftAbsolute"><p>{_esc(calendar.get("title", ""))}</p></div>
  <div class="calendarWeekHeader clip-box leftAbsolute">{''.join(f'<span>{_esc(day)}</span>' for day in weekdays)}</div>
  {''.join(week_rows)}
</div>"""


def _tasks_card(task: dict[str, Any], index: int) -> str:
    request = task.get("request") if isinstance(task.get("request"), dict) else {}
    finished = bool(task.get("finished"))
    suffix = "ed" if finished else "un"
    return f"""
<div class="abox">
  <div class="imgbox"><img src="{_esc(task.get("illustration", ""))}" alt="{_esc(task.get("song", ""))}"></div>
  <div class="coinbox_{suffix}"><p>+{_as_int(task.get("reward"))} Notes</p></div>
  <div class="infobox">
    <div class="namebox_{suffix}"><div class="songsname"><p id="{index}" name="pvis">{_esc(task.get("song", ""))}</p></div></div>
    <div class="songsinfo_{suffix}"><p>{_esc(request.get("rank", ""))}&ensp;&ensp;{_esc(str(request.get("type", "acc")).upper())}&ensp;&ensp;{_esc(request.get("value", ""))}</p></div>
  </div>
</div>"""


def _tasks_empty() -> str:
    return """
<div class="Nosignal">
  <div class="border_corner border_corner_left_top"></div>
  <div class="border_corner border_corner_right_top"></div>
  <div class="border_corner border_corner_left_bottom"></div>
  <div class="border_corner border_corner_right_bottom"></div>
  <div class="line"></div>
  <div class="timeout"><p>NOT_FOUND&ensp;&ensp;tip: try phi sign or phi retask</p></div>
  <div class="client"><p>>>> PhigrOS Client Finding Tasks</p></div>
  <div class="sqrt"><p>////////////////////////////////////////////////////////////////////////////////////////</p></div>
</div>"""


def info_html(
    paths: PluginPaths,
    summary: UserSummary,
    *,
    snapshot: SaveSnapshot,
    history: dict[str, Any] | None = None,
    catalog: SongCatalog | None = None,
    background: str | Path | None = None,
    variant: int = 1,
) -> str:
    gameuser = _gameuser(snapshot)
    stats = _info_stats(snapshot, summary, catalog)
    bksong = _source_data_uri(paths, background) if background is not None else ""
    if not bksong:
        bksong = _random_background(paths)
    userbackground = _info_background(paths, snapshot)
    rks_history, rks_range, rks_date = _info_series(paths, history or {}, "rks")
    data_history, data_range, data_date = _info_series(paths, history or {}, "data")
    acc_rks_data, acc_rks_range, acc_rks_AccRange = _info_acc_rks(snapshot, catalog)
    data = {
        "gameuser": {
            **gameuser,
            "backgroundurl": userbackground,
            "selfIntro": _info_intro(snapshot, summary),
        },
        "userstats": _info_userstats_list(stats),
        "rks_history": rks_history,
        "data_history": data_history,
        "rks_range": rks_range,
        "data_range": data_range,
        "data_date": [data_date[0], data_date[1]],
        "rks_date": [rks_date[0], rks_date[1]],
        "acc_rks_data": acc_rks_data,
        "acc_rks_range": acc_rks_range,
        "acc_rks_AccRange": acc_rks_AccRange,
        "background": bksong,
    }
    if variant == 2:
        return _userinfo_old_html(paths, data)
    return _userinfo_html(paths, data)


def _userinfo_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    gameuser = data["gameuser"]
    stats = data["userstats"]
    challenge_img = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    body = [
        _userinfo_layout_guard(),
        '<div class="background"><img src="{}" alt="{}"></div>'.format(_esc(data["background"]), _esc(data["background"])),
        '<div class="left">',
        '<div class="Player_Info"><p>PLAYER_INFO</p></div>',
        '<div class="Player_Info-after"></div>',
        '<div class="basic-box">',
        '<div class="basic-img"><img src="{}" alt="{}"></div>'.format(_esc(gameuser.get("backgroundurl", "")), _esc(gameuser.get("backgroundurl", ""))),
        '<div class="Player_Id">',
        '<div class="avatar"><img src="{}" alt="{}"></div>'.format(asset_uri(paths, "html/avatar/Introduction.png"), _esc(gameuser["avatar"])),
        '<div class="Player_Id-box">',
        '<div class="Player_Id-left"><p>ID</p></div>',
        '<div class="Player_Id-right"><p id="Player_Id" name="pvis">{}</p></div>'.format(_esc(gameuser["PlayerId"])),
        '</div></div></div>',
        '<div class="left_title"><div class="left_title-left"><p>PLAYER_DETAIL</p></div></div>',
        '<div class="Player_data_line">',
        f'<div class="Player_data_line-left"><div class="Player_data_title" id="Player_data_left"><p>RKS</p></div><div class="Player_data_value" id="Player_data_left"><p>{gameuser["rks"]:.4f}</p></div></div>',
        f'<div class="Player_data_line-right"><div class="Player_data_title" id="Player_data_right"><p>CLG MOD</p></div><div class="Challenge" id="Challenge2"><img src="{challenge_img}" alt="Challenge"><span>{gameuser["ChallengeModeRank"]}</span></div><div class="Player_data_value CLG colorful" id="Player_data_right"><p id="CLG">{_esc(gameuser.get("selfIntro", ""))}</p></div></div>',
        '</div>',
        f'<div class="Player_data_box" id="data_box"><div class="Player_box_title"><p>DATA</p></div><div class="Player_box_value"><p id="data">{_format_money_from_text(gameuser.get("data", ""))}</p></div></div>',
        '<div class="Player_profile_box"><font color="white" id="profile">{}</font></div>'.format(_esc(gameuser.get("selfIntro", ""))),
        '<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>',
        '</div>',
        '<div class="right">',
        _info_graph_block("RKS_HISTORY", data.get("rks_history", []), data.get("rks_range", [0, 1]), data.get("rks_date", ["", ""])),
        _info_graph_block("DATA_HISTORY", data.get("data_history", []), data.get("data_range", [0, 1]), data.get("data_date", ["", ""])),
        _info_limit_block(data.get("acc_rks_data", []), data.get("acc_rks_range", [0, 1]), data.get("acc_rks_AccRange", [])),
        _info_stats_block(paths, stats),
        '</div>',
    ]
    return original_page(paths, "userinfo/userinfo.css", "".join(body), theme="default", background=data["background"], width=1920)


def _userinfo_old_html(paths: PluginPaths, data: dict[str, Any]) -> str:
    gameuser = data["gameuser"]
    stats = data["userstats"]
    challenge_img = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    avatar_img = asset_uri(paths, "html/avatar/Introduction.png")
    profile = _safe(str(gameuser.get("selfIntro") or "")).replace("\n", "<br>")
    body = [
        _userinfo_old_layout_guard(),
        '<div class="basis-box" style="background-image:url(\'{}\')">'.format(_esc(gameuser.get("backgroundurl", ""))),
        '<div class="basis-box-out"><div class="box-in" id="basis">',
        '<div class="box-tatle"><p>Basis-Info</p></div>',
        '<div class="basis-info">',
        f'<div class="avatar"><img src="{avatar_img}" alt="{_esc(gameuser["avatar"])}"></div>',
        '<div class="name">',
        '<div class="user-info-line">',
        f'<div class="user-info-box"><div class="name-tatle"><p>Player ID</p></div><div class="name-value"><p name="pvis">{_esc(gameuser["PlayerId"])}</p></div></div>',
        f'<div class="Challenge"><img src="{challenge_img}" alt="Challenge"><p>{gameuser["ChallengeModeRank"]}</p></div>',
        '</div><div class="user-info-line">',
        f'<div class="user-info-box"><div class="name-tatle"><p>RankingScore</p></div><div class="name-value"><p>{gameuser["rks"]:.4f}</p></div></div>',
        f'<div class="user-info-box"><div class="name-tatle"><p>Data</p></div><div class="name-value"><p>{_format_money_from_text(gameuser.get("data", ""))}</p></div></div>',
        '</div></div></div>',
    ]
    if profile:
        body.extend([
            '<div class="box-tatle"><p>Profile</p></div>',
            f'<div class="profile"><font color="white">{profile}</font></div>',
        ])
    body.extend([
        '</div></div></div>',
        '<div class="box-out"><div class="box-in"><div class="box-tatle"><p>Stats</p></div>',
        _info_stats_block(paths, stats),
        '</div></div>',
        '<div class="box-out"><div class="box-in">',
        _info_old_graph_block("RKS History", data.get("rks_history", []), data.get("rks_range", [0, 1]), data.get("rks_date", ["", ""])),
        _info_old_graph_block("DATA History", data.get("data_history", []), data.get("data_range", [0, 1]), data.get("data_date", ["", ""])),
        '</div></div>',
        '<div class="createdbox"><div class="phi-plugin"><p>AstrBot Phi Plugin</p></div><div class="ver"><p>HTML</p></div></div>',
    ])
    return original_page(paths, "userinfo/userinfo-old.css", "".join(body), theme="default", background=data["background"], width=1800)


def _userinfo_layout_guard() -> str:
    return """
<style>
:root {
  --phi-viewport-width: 1920px;
  --phi-viewport-height: 1500px;
}
html, body {
  width: 1920px !important;
  min-width: 1920px !important;
  max-width: 1920px !important;
}
body {
  height: 1500px !important;
  min-height: 1500px !important;
  display: block !important;
}
.left {
  left: 2.5% !important;
  right: auto !important;
  top: 90px !important;
}
.right {
  right: 2.5% !important;
  left: auto !important;
  top: 90px !important;
}
.left,
.right {
  position: absolute !important;
  box-sizing: border-box !important;
}
</style>
"""


def _userinfo_old_layout_guard() -> str:
    return """
<style>
:root {
  --phi-viewport-width: 1800px;
}
html, body {
  width: 1800px !important;
  min-width: 1800px !important;
  max-width: 1800px !important;
}
body {
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
}
.basis-box {
  background-size: cover !important;
  background-position: top !important;
}
.stats-box {
  width: 100% !important;
}
</style>
"""


def _info_graph_block(title: str, lines: list[dict[str, Any]], value_range: list[float], date_text: list[str]) -> str:
    if not lines:
        return f'<div class="data_title"><div class="data_title-left"><p>{_esc(title)}</p></div></div><div class="svg-box"><p>NO_INFO</p></div>'
    svg_lines = "".join(
        f'<line x1="{line["x1"]}%" y1="{line["y1"]}%" x2="{line["x2"]}%" y2="{line["y2"]}%"></line>'
        for line in lines
    )
    values = "".join(f"<p>{_esc(v)}</p>" for v in reversed(value_range))
    dates = "".join(f"<p>{_esc(v)}</p>" for v in date_text)
    return (
        f'<div class="data_title"><div class="data_title-left"><p>{_esc(title)}</p></div></div>'
        '<div class="svg-box">'
        f'<div class="value_box">{values}</div>'
        '<div class="line-box"><div class="line"><svg><defs><marker id="dot" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="2" refY="2"><circle cx="2" cy="2" r="1"></circle></marker></defs>'
        f'{svg_lines}</svg></div><div class="date_box">{dates}</div></div>'
        '</div>'
    )


def _info_old_graph_block(title: str, lines: list[dict[str, Any]], value_range: list[float], date_text: list[str]) -> str:
    body = _info_graph_block(title, lines, value_range, date_text)
    return f'<div class="box-tatle"><p>{_esc(title)}</p></div>{body}'


def _info_limit_block(data_rows: list[dict[str, Any]], value_range: list[float], positions: list[dict[str, Any]]) -> str:
    if not data_rows:
        return ""
    values = "".join(f"<p>{_esc(v)}</p>" for v in reversed(value_range))
    dates = "".join(f"<p>{_esc(v)}</p>" for v in positions)
    lines = "".join(
        f'<line x1="{line["x1"]}%" y1="{line["y1"]}%" x2="{line["x2"]}%" y2="{line["y2"]}%"></line>'
        for line in data_rows
    )
    return (
        '<div class="data_title"><div class="data_title-left"><p>Limit-ACC_RKS</p></div><p>将您成绩中所有 ACC 低于某一横轴值的记录剔除后重新计算 RKS</p></div>'
        '<div class="svg-box">'
        f'<div class="value_box">{values}</div>'
        '<div class="line-box"><div class="line"><svg><defs><marker id="dot" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="2" refY="2"><circle cx="0" cy="0" r="0"></circle></marker></defs>'
        f'{lines}</svg><div class="vis_dot_box"><div class="vis_dot"></div></div></div><div class="date_box">{dates}</div></div>'
        '</div>'
    )


def _info_stats_block(paths: PluginPaths, stats: dict[str, Any]) -> str:
    blocks = []
    for block in stats:
        rank = block.get("title", "")
        rating_img = asset_uri(paths, f"html/otherimg/{block.get('rating', 'V')}.png")
        blocks.append(
            '<div class="one-stats-box">'
            f'<div class="rank"><p>{rank}</p></div>'
            '<div class="stats-up">'
            f'<div class="Rating"><img src="{rating_img}" alt="{rank}"></div>'
            f'<div class="stats-group"><div class="stats-group-real"><p>{block.get("played", 0)}</p></div><div class="stats-group-tot"><p>/{block.get("total", 0)}</p></div></div>'
            '<div class="stats-rating-group">'
            f'<div class="rating-group"><div class="rating-value"><p>{block.get("cleared", 0)}</p></div><div class="rating-tatle"><p>Cleared</p></div></div>'
            f'<div class="rating-group"><div class="rating-value"><p>{block.get("fc", 0)}</p></div><div class="rating-tatle"><p>FC</p></div></div>'
            f'<div class="rating-group"><div class="rating-value"><p>{block.get("phi", 0)}</p></div><div class="rating-tatle"><p>PHI</p></div></div>'
            '</div></div>'
            f'<div class="stats-group"><div class="stats-group-real"><p>{block.get("score", 0)}</p></div><div class="stats-group-tot"><p>/200000000</p></div></div>'
            f'<div class="stats-score"><div class="stats-group"><div class="stats-group-real"><p>{block.get("highest", 0):.1f}</p></div><div class="stats-group-tot"><p>Highest</p></div></div><div class="stats-group"><div class="stats-group-real"><p>{block.get("lowest", 0):.1f}</p></div><div class="stats-group-tot"><p>lowest</p></div></div></div>'
            '</div>'
        )
    return '<div class="stats-box">' + "".join(blocks) + "</div>"


def _info_background(paths: PluginPaths, snapshot: SaveSnapshot) -> str:
    song = str((snapshot.raw.get("gameuser") or {}).get("background") or "")
    if not song or song.casefold() == "introduction":
        return asset_uri(paths, "html/otherimg/phigros.png") or _random_background(paths)
    if song:
        path = find_background_illustration_file(paths, song)
        if path is not None:
            return _illustration_source(paths, path, song_id=song, background=True)
        if use_remote_illustrations(paths) and is_known_online_illustration_id(paths, song):
            return background_illustration_url(song, paths=paths)
    return asset_uri(paths, "html/otherimg/phigros.png") or _random_background(paths)


def _ranking_large_line(paths: PluginPaths, me: dict[str, Any], catalog: SongCatalog | None) -> dict[str, Any]:
    raw_save = me.get("save") if isinstance(me.get("save"), dict) else me
    snapshot = _snapshot_from_rank_save(raw_save)
    if snapshot is None:
        return {
            "backgroundurl": _random_background(paths),
            "updated": "NO INFO",
            "selfIntro": "",
            "rks_history": [],
            "rks_range": [0.0, 0.0],
            "rks_date": ["", ""],
            "b30list": _ranking_empty_b30_groups(),
            "clg_list": [],
        }
    history = me.get("history") if isinstance(me.get("history"), dict) else {}
    b30 = compute_rank_b30(snapshot, catalog) if catalog is not None else None
    rks_history, rks_range, rks_date = _series_lines(
        history,
        "rks",
        current=(_date_label(extract_modified_datetime(snapshot.raw)), snapshot.ranking_score),
    )
    return {
        **_ranking_small_line(paths, raw_save, fallback_index=0, catalog=catalog),
        "backgroundurl": _rank_background(paths, raw_save, catalog),
        "updated": format_datetime(extract_modified_datetime(snapshot.raw)),
        "selfIntro": str(_rank_gameuser(raw_save).get("selfIntro") or ""),
        "rks_history": rks_history,
        "rks_range": rks_range,
        "rks_date": [rks_date[0], rks_date[1]],
        "b30list": _ranking_b30_lists(b30) if b30 is not None else _ranking_empty_b30_groups(),
        "clg_list": _ranking_challenge_list(history),
    }


def _ranking_small_line(
    paths: PluginPaths,
    raw: dict[str, Any],
    *,
    fallback_index: int,
    catalog: SongCatalog | None,
) -> dict[str, Any]:
    save_info = _rank_save_info(raw)
    summary = save_info.get("summary") if isinstance(save_info.get("summary"), dict) else {}
    gameuser = _rank_gameuser(raw)
    challenge = _as_int(summary.get("challengeModeRank") or gameuser.get("challengeModeRank"))
    avatar = _avatar_name(paths, str(summary.get("avatar") or gameuser.get("avatar") or "Introduction"))
    rks = _as_float(summary.get("rankingScore") or gameuser.get("rankingScore") or raw.get("rks")) or 0.0
    return {
        "backgroundurl": _rank_background(paths, raw, catalog),
        "avatar": avatar,
        "playerId": str(save_info.get("PlayerId") or gameuser.get("PlayerId") or gameuser.get("name") or "NO INFO"),
        "rks": rks,
        "ChallengeMode": max(0, min(5, challenge // 100)),
        "ChallengeModeRank": challenge % 100,
        "index": _as_int(raw.get("index")) or fallback_index,
        "me": bool(raw.get("me")),
    }


def _ranking_user_html(paths: PluginPaths, user: dict[str, Any]) -> str:
    background = str(user.get("backgroundurl") or "")
    if not background:
        return '<div class="aUser"><div class="playerId"><p name="pvis">NO INFO</p></div></div>'
    avatar = str(user.get("avatar") or "Introduction")
    avatar_uri = asset_uri(paths, f"html/avatar/{avatar}.png") or asset_uri(paths, "html/avatar/Introduction.png")
    challenge_uri = asset_uri(paths, f"html/otherimg/{_as_int(user.get('ChallengeMode'))}.png")
    you = " you" if user.get("me") else ""
    profile_img = "" if user.get("me") else f'<img src="{_esc(background)}" alt="{_esc(background)}">'
    return f"""
<div class="aUser{you}">
  <div class="profileIll">{profile_img}</div>
  <div class="avatar_box"><div class="avatar"><img src="{avatar_uri}" alt="{_esc(avatar)}"></div></div>
  <div class="num"><p>#{_as_int(user.get("index"))}</p></div>
  <div class="playerId"><p name="pvis">{_esc(user.get("playerId", "NO INFO"))}</p></div>
  <div class="clgBox"><div class="Challenge"><img src="{challenge_uri}" alt="Challenge"><p>{_as_int(user.get("ChallengeModeRank"))}</p></div></div>
  <div class="rks"><p>{float(user.get("rks") or 0):.4f}</p></div>
</div>"""


def _ranking_challenge_list(history: dict[str, Any]) -> list[dict[str, Any]]:
    raw = history.get("challengeModeRank") if isinstance(history.get("challengeModeRank"), list) else []
    result: list[dict[str, Any]] = []
    previous: int | None = None
    for item in raw:
        if not isinstance(item, dict):
            continue
        value = _as_int(item.get("value"))
        if previous is not None and value == previous:
            continue
        previous = value
        result.append({
            "ChallengeMode": max(0, min(5, value // 100)),
            "ChallengeModeRank": value % 100,
            "date": _date_label(item.get("date")),
        })
    return result[-8:]


def _ranking_challenge_history(paths: PluginPaths, item: dict[str, Any]) -> str:
    challenge_uri = asset_uri(paths, f"html/otherimg/{_as_int(item.get('ChallengeMode'))}.png")
    return f"""
<div class="a_clg_box">
  <div class="clg_box"><div class="Challenge"><img src="{challenge_uri}" alt="Challenge"><p>{_as_int(item.get("ChallengeModeRank"))}</p></div></div>
  <p>{_esc(item.get("date", ""))}</p>
</div>"""


def _ranking_b30_lists(result: Best30Result) -> list[dict[str, Any]]:
    return [
        {"key": "P3", "title": "Perfect 3", "list": result.phi_records[:3]},
        {"key": "B3", "title": "Best 3", "list": result.records[:3]},
        {"key": "F3", "title": "Floor 3", "list": result.records[24:27]},
        {"key": "L3", "title": "Overflow 3", "list": result.records[27:30]},
    ]


def _ranking_empty_b30_groups() -> list[dict[str, Any]]:
    return [
        {"key": "P3", "title": "Perfect 3", "list": []},
        {"key": "B3", "title": "Best 3", "list": []},
        {"key": "F3", "title": "Floor 3", "list": []},
        {"key": "L3", "title": "Overflow 3", "list": []},
    ]


def _ranking_b30_group(paths: PluginPaths, group: dict[str, Any]) -> str:
    records = group.get("list") if isinstance(group.get("list"), list) else []
    cards = [_ranking_b30_card(paths, record) for record in records[:3] if isinstance(record, ScoreRecord)]
    while len(cards) < 3:
        cards.append('<div class="ill_box"><p>NO INFO</p></div>')
    return f"""
<div class="b30Alist {_esc(group.get("key", ""))}">
  <p>{_esc(group.get("title", ""))}</p>
  {''.join(cards)}
</div>"""


def _ranking_b30_card(paths: PluginPaths, record: ScoreRecord) -> str:
    rating = _rating_asset(record.rating)
    rating_uri = asset_uri(paths, f"html/otherimg/{rating}.png")
    return f"""
<div class="ill_box">
  <img src="{_record_illustration(paths, record)}" alt="{_esc(record.song_title)}">
  <div class="b30_dif {record.rank}-BKG"><p>{_esc(record.rank)} {record.difficulty:.1f}</p></div>
  <div class="Rating"><img src="{rating_uri}" alt="{_esc(rating)}"></div>
</div>"""


def _snapshot_from_rank_save(raw_save: Any) -> SaveSnapshot | None:
    if not isinstance(raw_save, dict):
        return None
    save_info = _rank_save_info(raw_save)
    summary = save_info.get("summary") if isinstance(save_info.get("summary"), dict) else {}
    if not isinstance(save_info, dict) or not summary:
        return None
    return SaveSnapshot(
        user_id="ranklist",
        session_token=str(raw_save.get("session") or ""),
        player_id=str(save_info.get("PlayerId") or ""),
        player_name=str(_rank_gameuser(raw_save).get("name") or save_info.get("PlayerId") or ""),
        ranking_score=_as_float(summary.get("rankingScore")) or 0.0,
        challenge_mode_rank=summary.get("challengeModeRank"),
        game_version=summary.get("gameVersion"),
        raw=raw_save,
    )


def compute_rank_b30(snapshot: SaveSnapshot, catalog: SongCatalog | None) -> Best30Result:
    if catalog is None:
        return Best30Result(snapshot.ranking_score, 0.0, [], 0, [])
    records = sorted(iter_score_records(snapshot, catalog), key=lambda item: item.rks, reverse=True)
    phi_records = sorted((record for record in records if record.acc >= 100), key=lambda item: item.rks, reverse=True)[:3]
    computed_records = [*phi_records, *records[:27]]
    computed = sum(record.rks for record in computed_records) / 30 if computed_records else 0.0
    return Best30Result(snapshot.ranking_score, computed, records[:33], len(records), phi_records)


def _rank_save_info(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("saveInfo")
    return value if isinstance(value, dict) else {}


def _rank_gameuser(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("gameuser")
    return value if isinstance(value, dict) else {}


def _rank_background(paths: PluginPaths, raw: dict[str, Any], catalog: SongCatalog | None) -> str:
    gameuser = _rank_gameuser(raw)
    raw_background = str(gameuser.get("background") or raw.get("backgroundurl") or raw.get("background") or "").strip()
    if raw_background:
        uri = _source_data_uri(paths, raw_background)
        if uri:
            return uri
        for song_id in _background_song_id_candidates(raw_background, catalog):
            path = find_background_illustration_file(paths, song_id)
            if path is not None:
                return _illustration_source(paths, path, song_id=song_id, background=True)
            if use_remote_illustrations(paths):
                return background_illustration_url(song_id, paths=paths)
            song = catalog.get(song_id) if catalog is not None else None
            if song is not None:
                return _song_illustration(paths, song)
    return _random_background(paths)


def _background_song_id_candidates(value: str, catalog: SongCatalog | None) -> list[str]:
    candidates = [
        value,
        value.removesuffix(".0"),
        value.replace("Another Me ", "Another Me (KALPA)"),
        value.replace("Another Me", "Another Me (Rising Sun Traxx)") if value == "Another Me" else value,
        value.replace("Re_Nascence (Psystyle Ver.) ", "Re_Nascence (Psystyle Ver.)"),
        value.replace("Energy Synergy Matrix", "ENERGY SYNERGY MATRIX"),
        value.replace("Le temps perdu-", "Le temps perdu"),
    ]
    if catalog is not None:
        key = normalize_song_key(value)
        song_id = catalog.alias_to_id.get(key)
        if song_id:
            candidates.append(song_id)
    result: list[str] = []
    for item in candidates:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _avatar_name(paths: PluginPaths, avatar: str) -> str:
    if avatar == "Cipher : /2&//<|0":
        avatar = "Cipher1"
    elif avatar == "Oblivion: PHIN":
        avatar = "OblivionPHIN"
    path = paths.resources / "html" / "avatar" / f"{avatar}.png"
    return avatar if path.exists() else "Introduction"


def _info_intro(snapshot: SaveSnapshot, summary: UserSummary) -> str:
    intro = (snapshot.raw.get("gameuser") or {}).get("selfIntro")
    if intro:
        return str(intro)
    return f"Total Records: {summary.total_records}"


def _info_stats(snapshot: SaveSnapshot, summary: UserSummary, catalog: SongCatalog | None) -> dict[str, Any]:
    by_rank = {
        rank: {
            "played": 0,
            "total": 0,
            "cleared": 0,
            "fc": 0,
            "phi": 0,
            "score": 0,
            "highest": 0.0,
            "lowest": 0.0,
            "rating": "V",
        }
        for rank in LEVELS
    }
    records = iter_score_records(snapshot, catalog) if catalog is not None else []
    record_map = {(record.song_id, record.rank): record for record in records}
    if catalog is not None:
        for song in catalog.all_songs():
            for chart in song.display_charts():
                if chart.rank not in by_rank:
                    continue
                item = by_rank[chart.rank]
                item["total"] += 1
                record = record_map.get((song.id, chart.rank))
                if record is None:
                    continue
                _apply_info_record_stat(item, record)
    else:
        for record in records:
            if record.rank in by_rank:
                item = by_rank[record.rank]
                item["total"] += 1
                _apply_info_record_stat(item, record)
    for rank, item in by_rank.items():
        if item["played"] and not item["lowest"]:
            item["lowest"] = item["highest"]
        item["rating"] = _dominant_rating(records, rank)
    return by_rank


def _info_userstats_list(stats: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rank in ("AT", "IN", "HD", "EZ"):
        item = stats.get(rank, {})
        result.append({
            "title": rank,
            "Rating": item.get("rating", "V"),
            "unlock": item.get("played", 0),
            "tot": item.get("total", 0),
            "cleared": item.get("cleared", 0),
            "fc": item.get("fc", 0),
            "phi": item.get("phi", 0),
            "real_score": item.get("score", 0),
            "tot_score": max(1, int(item.get("total", 0)) * 1_000_000),
            "highest": float(item.get("highest", 0.0)),
            "lowest": float(item.get("lowest", 0.0)),
        })
    return result


def _apply_info_record_stat(item: dict[str, Any], record: ScoreRecord) -> None:
    item["played"] += 1
    item["cleared"] += 1
    item["fc"] += 1 if record.fc or record.rating == "phi" else 0
    item["phi"] += 1 if record.rating == "phi" else 0
    item["score"] += record.score
    item["highest"] = max(float(item["highest"]), record.difficulty)
    item["lowest"] = record.difficulty if not item["lowest"] else min(float(item["lowest"]), record.difficulty)


def _dominant_rating(records: list[ScoreRecord], rank: str) -> str:
    ratings = Counter(record.rating for record in records if record.rank == rank)
    if not ratings:
        return "V"
    order = {"phi": 7, "FC": 6, "V": 5, "S": 4, "A": 3, "B": 2, "C": 1, "F": 0, "NEW": -1}
    return max(ratings, key=lambda key: (ratings[key], order.get(key, -2)))


def _update_graph_inner(lines: list[dict[str, Any]], value_range: list[float], date_text: list[str]) -> str:
    if not lines:
        return "<p>NO_INFO</p>"
    values = "".join(f"<p>{_esc(f'{value:.4f}' if isinstance(value, float) else value)}</p>" for value in reversed(value_range))
    dates = "".join(f"<p>{_esc(value)}</p>" for value in date_text)
    svg_lines = "".join(
        f'<line x1="{line["x1"]}%" y1="{line["y1"]}%" x2="{line["x2"]}%" y2="{line["y2"]}%"></line>'
        for line in lines
    )
    return (
        f'<div class="value_box">{values}</div>'
        '<div class="line-box"><div class="line"><svg><defs><marker id="dot" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="2" refY="2"><circle cx="2" cy="2" r="1"></circle></marker></defs>'
        f'{svg_lines}</svg></div><div class="date_box">{dates}</div></div>'
    )


def _info_series(paths: PluginPaths, history: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], list[float], list[str]]:
    return _series_lines(history, key, money=key == "data")


def _info_acc_rks(snapshot: SaveSnapshot, catalog: SongCatalog | None) -> tuple[list[dict[str, Any]], list[float], list[str]]:
    if catalog is None:
        return [], [0.0, 1.0], []
    records = sorted(iter_score_records(snapshot, catalog), key=lambda item: item.rks, reverse=True)
    phi_records = sorted((record for record in records if record.acc >= 100), key=lambda item: item.rks, reverse=True)[:3]
    phi_rks = sum(record.rks for record in phi_records)
    b27_source = records[:27]
    if not b27_source:
        return [], [0.0, 1.0], []
    min_acc = min(record.acc for record in b27_source)
    samples: list[tuple[float, float]] = []
    step_count = 40
    for index in range(step_count + 1):
        threshold = min_acc + (100.0 - min_acc) * index / step_count
        filtered = [record for record in b27_source if record.acc >= threshold][:27]
        rks = (phi_rks + sum(record.rks for record in filtered)) / 30 if filtered or phi_records else 0.0
        samples.append((threshold, rks))
    lines, value_range, _ = _numeric_series_to_lines(samples, value_format="{:.4f}")
    labels = _acc_labels(min_acc)
    return lines, value_range, labels


def _series_lines(
    history: dict[str, Any],
    key: str,
    *,
    current: tuple[str, Any] | None = None,
    money: bool = False,
) -> tuple[list[dict[str, Any]], list[float], list[str]]:
    raw_series = history.get(key) if isinstance(history.get(key), list) else []
    points: list[tuple[str, float]] = []
    for item in raw_series:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        number = money_to_kib(value) if money else _as_float(value)
        if number is None:
            continue
        points.append((_date_label(item.get("date")), float(number)))
    if current is not None:
        current_number = money_to_kib(current[1]) if money else _as_float(current[1])
        if current_number is not None and not any(label == current[0] for label, _ in points):
            points.append((current[0], float(current_number)))
    points = _sample_series_points(points, max_points=96)
    if len(points) < 2:
        return [], [0.0, 0.0], ["", points[-1][0] if points else ""]
    lines, value_range, date_range = _numeric_series_to_lines([(index, value) for index, (_, value) in enumerate(points)])
    return lines, value_range, [points[0][0], points[-1][0]]


def _sample_series_points(points: list[tuple[str, float]], *, max_points: int) -> list[tuple[str, float]]:
    if len(points) <= max_points:
        return points
    sampled: list[tuple[str, float]] = []
    last_index = len(points) - 1
    for sample_index in range(max_points):
        source_index = round(sample_index * last_index / (max_points - 1))
        point = points[source_index]
        if not sampled or sampled[-1] != point:
            sampled.append(point)
    return sampled


def _numeric_series_to_lines(
    points: list[tuple[float, float]],
    *,
    value_format: str = "{:.4f}",
) -> tuple[list[dict[str, Any]], list[float], list[str]]:
    if len(points) < 2:
        return [], [0.0, 0.0], ["", ""]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    x_span = max(max_x - min_x, 1e-9)
    y_span = max(max_y - min_y, 1e-9)
    result = []
    for left, right in zip(points, points[1:]):
        x1 = (left[0] - min_x) / x_span * 100
        x2 = (right[0] - min_x) / x_span * 100
        y1 = 100 - (left[1] - min_y) / y_span * 100
        y2 = 100 - (right[1] - min_y) / y_span * 100
        result.append({"x1": f"{x1:.4f}", "y1": f"{y1:.4f}", "x2": f"{x2:.4f}", "y2": f"{y2:.4f}"})
    return result, [min_y, max_y], ["", ""]


def _acc_labels(min_acc: float) -> list[str]:
    labels = [min_acc]
    step = max((100.0 - min_acc) / 5, 0.01)
    value = min_acc + step
    while value < 99.99:
        labels.append(value)
        value += step
    labels.append(100.0)
    return [f"{value:.2f}%" for value in labels]


def _date_label(value: Any) -> str:
    if isinstance(value, str):
        return value.replace("T", " ").replace("+00:00", "").split(".", 1)[0]
    if isinstance(value, datetime):
        return format_datetime(value)
    return str(value or "")


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _update_box_lines(paths: PluginPaths, days: list[ProgressDay]) -> list[list[dict[str, Any]]]:
    box_line: list[list[dict[str, Any]]] = []
    for day in days:
        songs = [_update_change_song(paths, change) for change in day.changes]
        if not songs:
            continue
        box_line.append([{
            "date": day.date,
            "color": "#fff382",
            "update_num": day.update_count,
            "width": max(135, min(755, len(songs) * 155 - 20)),
            "song": songs,
        }])
    return box_line


def _update_record_box_html(box_line: list[list[dict[str, Any]]]) -> str:
    if not box_line:
        return """
<div class="Nosignal">
  <div class="border_corner border_corner_left_top"></div>
  <div class="border_corner border_corner_right_top"></div>
  <div class="border_corner border_corner_left_bottom"></div>
  <div class="border_corner border_corner_right_bottom"></div>
  <div class="line"></div>
  <div class="timeout"><p>NOT_FOUND</p></div>
  <div class="client"><p>>>> PhigrOS Client Finding NewScore</p></div>
  <div class="sqrt"></div>
</div>"""
    rows = ['<div class="record_box">']
    for time_line in box_line:
        rows.append('<div class="title_box">')
        for date in time_line:
            update_num = _as_int(date.get("update_num"))
            update_label = ""
            if update_num > 1:
                update_label = f'<div class="box_title-right"><p name="pvis">Updated x {update_num}</p></div>'
            rows.append(
                f'<div class="box_title" style="width: {int(date["width"])}px;filter: drop-shadow(0px 2px 2px {date["color"]});">'
                f'<div class="box_title-right-down" style="background-color: {date["color"]};"></div>'
                f'<div class="box_title-left" style="background-color: {date["color"]};"><p name="pvis">{_esc(date.get("date", ""))}</p></div>'
                f"{update_label}</div>"
            )
        rows.append('</div>')
        rows.append('<div class="song_box">')
        for date in time_line:
            for song in date.get("song", []):
                rows.append(_update_song_card(song))
        rows.append('</div>')
    rows.append('</div>')
    return "".join(rows)


def _update_change_song(paths: PluginPaths, change: ProgressScoreChange) -> dict[str, Any]:
    acc_int = int(change.acc_new)
    acc_frac = f"{change.acc_new % 1:.4f}".replace("0.", "")
    score_delta = ""
    if change.score_old is not None:
        delta = change.score_new - change.score_old
        if delta:
            score_delta = f"{delta:+,}"
    rks = f"{change.rks_new:.4f}" if change.rks_new else ""
    ill_path = find_illustration_file(paths, change.song_id, prefer_low=True)
    illustration = _illustration_source(paths, ill_path, song_id=change.song_id, prefer_low=True) if ill_path is not None else (
        illustration_url(change.song_id, prefer_low=True, paths=paths) if use_remote_illustrations(paths) else asset_uri(paths, "html/otherimg/phigros.png")
    )
    rating_img = ""
    if change.rating_new:
        rating = asset_uri(paths, f"html/otherimg/{change.rating_new}.png")
        rating_img = f'<div class="new-box"><img src="{rating}" alt="{_esc(change.rating_new)}"></div>'
    return {
        "illustration": illustration,
        "song": change.song_title,
        "rank": change.rank,
        "score_new": change.score_new,
        "acc_new": change.acc_new,
        "rks_new": change.rks_new,
        "Rating": change.rating_new,
        "rating_img": rating_img,
        "score_delta": score_delta,
    }


def _update_song_card(song: dict[str, Any]) -> str:
    acc = float(song.get("acc_new") or 0)
    acc_int = int(acc)
    acc_frac = f"{acc % 1:.4f}".replace("0.", "")
    rks = f"{float(song.get('rks_new') or 0):.4f}" if song.get("rks_new") else ""
    return f"""
<div class="abox">
  <div class="imgbox"><img src="{song.get('illustration', '')}" alt="{_esc(song.get('song', ''))}"></div>
  {'<div class="coinbox"><p>' + _esc(song.get('score_delta', '')) + '</p></div>' if song.get('score_delta') else ''}
  <div class="infobox">
    <div class="namebox">
      {song.get('rating_img', '')}
      <div class="songsname"><p name="pvis">{_esc(song.get('song', ''))}</p></div>
    </div>
    <div class="songsinfo">
      <div class="rank"><p>{_esc(song.get('rank', ''))}</p></div>
      <div class="score"><p>{int(song.get('score_new') or 0):,}</p></div>
      <div class="acc"><div class="acc_1"><p>{acc_int}</p></div><div class="acc_2"><p>.{acc_frac}%</p></div></div>
      {'<div class="rks"><p>' + _esc(rks) + '</p></div>' if rks else ''}
    </div>
  </div>
</div>"""


def _delta_span(value: str) -> str:
    if not value:
        return ""
    color = "gold" if value.startswith("+") else "red"
    return f' <span style="color: {color};">{_esc(value)}</span>'


def _signed_delta(value: int | float | None, *, digits: int = 4, suffix: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = f"{value:+.{digits}f}"
    else:
        text = f"{value:+d}"
    return f"{text}{suffix}"


def _format_money_from_text(value: str) -> str:
    return value if value else "0KiB"


def original_page(paths: PluginPaths, css_rel: str | tuple[str, ...], body: str, *, theme: str = "star", background: str = "", width: int = 1200) -> str:
    star1 = asset_uri(paths, "html/otherimg/Star1.png")
    star2 = asset_uri(paths, "html/otherimg/Star2.png")
    fallback = asset_uri(paths, "html/otherimg/phigros.png")
    page_background = background or fallback
    background_html = f"""
    <div class="background">
      {'<img src="' + star1 + '" alt="曲绘-模糊"><img src="' + star2 + '" alt="曲绘-模糊" style="min-height:0;width:100%;height:auto;bottom:0;filter:none;">' if theme == "star" else '<img src="' + page_background + '" alt="曲绘-模糊">'}
    </div>
    """
    theme_script = '<script>{}</script>'.format(_js_text(paths, "html/common/theme/star/star.js")) if theme == "star" else ""
    theme_body = '<canvas id="stars"></canvas><script>themeStar();</script>' if theme == "star" else ""
    return f"""<!DOCTYPE html>
<html lang="zh-cn">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={int(width)}">
  <link rel="shortcut icon" href="#">
  <style>{_css_text(paths, "html/common/common.css")}</style>
  <style>{_css_bundle(paths, css_rel)}</style>
  <style>{_render_reset_css(page_background if theme != "star" else "", width=int(width))}</style>
  <title>phi-plugin</title>
</head>
<body class="elem-hydro default-mode">
  {background_html}
  <script>var _res_path = "";</script>
  {theme_script}
  {body}
  {theme_body}
  <script>{_auto_font_script()}</script>
</body>
</html>"""


def asset_uri(paths: PluginPaths, relative: str) -> str:
    base = paths.resources
    if relative:
        base = base / relative
    return _file_data_uri(base)


def image_data_uri(paths: PluginPaths, source: str | Path) -> str:
    return _source_data_uri(paths, source)


def _notice_items(notice: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(notice, dict) or not notice:
        return []
    for key in ("info", "notices", "list", "data"):
        value = notice.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    return [notice]


def _notice_content_lines(content: Any) -> list[str]:
    if isinstance(content, list):
        return [str(item) for item in content]
    if content is None:
        return []
    return str(content).replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n").splitlines()


def _notice_date_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        import datetime as _dt

        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return _dt.datetime.fromtimestamp(timestamp).strftime("%m-%d")
        except (OSError, ValueError):
            return ""
    return str(value)


def _b30_title(
    paths: PluginPaths,
    gameuser: dict[str, Any],
    stats: list[dict[str, Any]],
    date_text: str,
    sp_info: list[str] | None = None,
) -> str:
    avatar_path = paths.resources / "html" / "avatar" / f"{gameuser['avatar']}.png"
    avatar = _file_data_uri(avatar_path) or asset_uri(paths, "html/avatar/Introduction.png")
    challenge = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    data_img = asset_uri(paths, "html/otherimg/data.png")
    stat_headers = "".join(f'<div class="poz"><p>{_esc(item["title"])}</p></div>' for item in stats)
    cleared = "".join(f'<div class="poz"><p>{item["cleared"]}</p></div>' for item in stats)
    fc = "".join(f'<div class="poz"><p>{item["fc"]}</p></div>' for item in stats)
    phi = "".join(f'<div class="poz"><p>{item["phi"]}</p></div>' for item in stats)
    sp_info_html = ""
    if sp_info:
        chips = "".join(f'<div class="spInfo colorful-background clip-box"><p>{_esc(item)}</p></div>' for item in sp_info)
        sp_info_html = f'<div class="spInfoBox">{chips}</div>'
    return f"""
<div class="title">
  <div class="playerInfo">
    <div class="blackBlock clip-box"></div>
    <div class="avatar clip-box"><img src="{avatar}" alt="{_esc(gameuser['avatar'])}"></div>
    <div class="playerId"><p name="pvis">{_esc(gameuser['PlayerId'])}</p></div>
    <div class="rks clip-box"><p>{float(gameuser['rks']):.4f}</p></div>
    <div class="clgBox"><div class="Challenge"><img src="{challenge}" alt="Challenge"><p>{gameuser['ChallengeModeRank']}</p></div></div>
    <div class="date"><p>{_esc(date_text)}</p></div>
    <div class="dataBox clip-box"><img src="{data_img}" alt="data"><p>{_esc(gameuser['data'])}</p></div>
    {sp_info_html}
  </div>
  <div class="recordInfo clip-box">
    <div class="whiteLine clip-box"></div>
    <div class="sheet">
      <div class="row"><div class="poz"><p>\\</p></div>{stat_headers}</div>
      <div class="row"><div class="poz"><p>C</p></div>{cleared}</div>
      <div class="row"><div class="poz"><p>FC</p></div>{fc}</div>
      <div class="row"><div class="poz"><p>Phi</p></div>{phi}</div>
    </div>
  </div>
</div>"""


def _dss2_title(
    paths: PluginPaths,
    gameuser: dict[str, Any],
    title: str,
    header_ill: str,
    sp_info: list[str],
) -> str:
    challenge = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    data_img = asset_uri(paths, "html/otherimg/data.png")
    sp_info_html = "".join(
        f'<div class="spInfo colorful-background clip-box"><p>{_esc(item)}</p></div>'
        for item in sp_info
    )
    return f"""
<div class="title">
  <div class="gameuser_background">
    <div class="gameuser_background_cover_block"></div>
    <img src="{header_ill}" alt="BS">
  </div>
  <div class="frontBlock"></div>
  <div class="phigrosTitle">
    <div class="blackBar clip-box-right"></div>
    <p>Phigros</p>
  </div>
  <div class="titleDesc"><p class="weight-font">{_esc(title)}</p></div>
  <div class="titlePlayerInfo">
    <div class="playerId"><p name="pvis" class="weight-font">{_esc(gameuser['PlayerId'])}</p></div>
    <div class="rks">
      <div class="clgBox">
        <div class="Challenge"><img src="{challenge}" alt="Challenge"><p>{gameuser['ChallengeModeRank']}</p></div>
      </div>
      <p class="weight-font">{float(gameuser['rks']):.4f}</p>
    </div>
  </div>
  <div class="backBlockBox">
    <div class="backBlock1"></div>
    <div class="backBlock2"></div>
    <div class="backBlock3">
      <div class="dataBox clip-box"><img src="{data_img}" alt="data"><p>{_esc(gameuser['data'])}</p></div>
      {sp_info_html}
    </div>
  </div>
</div>"""


def _dss2_record_card(paths: PluginPaths, record: ScoreRecord, number: str, *, highlighted: bool) -> str:
    rating = asset_uri(paths, f"html/otherimg/{record.rating}.png")
    illustration = _record_illustration(paths, record)
    css_class = "song b_song" if highlighted else "song"
    return f"""
<div class="{css_class}">
  <div class="leftBar clip-box"></div>
  <div class="numBox">
    <p class="weight-font">{_esc(number)}</p>
    <p>{_esc(number)}</p>
    <p>{_esc(number)}</p>
  </div>
  <div class="starBox"><div class="star"></div></div>
  <div class="rank-{_esc(record.rank)} clip-box">
    <div class="org"><p>{_esc(record.rank)}&ensp;{record.difficulty:.1f}</p></div>
    <div class="rel"><p>{record.rks:.2f}</p></div>
  </div>
  <div class="ill clip-box"><img src="{illustration}" alt="ill"></div>
  <div class="info-AT">
    <div class="songname"><p name="pvis">{_esc(record.song_title)}</p></div>
    <div class="acc-box">
      <div class="acc"><p>{record.acc:.2f}%</p></div>
      <div class="suggest suggest-kind-{_record_list_suggest_type(record)}">
        <div class="suggest-tip"></div>
        <p>{_record_list_suggest(record)}</p>
      </div>
    </div>
    <div class="chengji">
      <div class="score"><p>{record.score:,}</p></div>
      <div class="line"></div>
      <div class="Rating"><img src="{rating}" alt="{_esc(record.rating)}"></div>
    </div>
  </div>
</div>"""


def _score_list_line(paths: PluginPaths, entry: ScoreListEntry, index: int) -> str:
    chart = entry.chart
    record = entry.record
    if record is None:
        score = "NEW"
        acc = None
        suggest = "---"
        rating = "NEW"
    else:
        score = f"{record.score:,}"
        acc = record.acc
        suggest = f"RKS {record.rks:.4f}"
        rating = _rating_asset(record.rating)
    song = _esc(_song_display_name(paths, chart.song_id, chart.song_title))
    composer = _esc(_song_composer(paths, chart.song_id))
    return f"""
<div class="line">
  <div class="song_name">
    <div class="num"><span name="pvis">{index}</span></div>
    <div class="song"><span name="pvis">{song}{' - ' + composer if composer else ''}</span></div>
    <div class="dif {_esc(chart.rank)}"><span name="pvis">{chart.difficulty:.1f}</span></div>
  </div>
  <div class="ill_box"><img src="{_chart_illustration(paths, chart)}" alt="{song}"></div>
  <div class="info_box"><div class="down">
    <div class="acc"><div class="box-content">{'---' if acc is None else f'{acc:.4f}'}%</div><div class="suggest">&gt; {_esc(suggest)}</div></div>
    <div class="score_rating"><div class="score">{_esc(score)}</div><div class="rating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div></div>
  </div></div>
</div>"""


def _suggest_line(paths: PluginPaths, entry: SuggestEntry, index: int, kind: str) -> str:
    chart = entry.chart
    current = entry.current
    rating = _rating_asset(current.rating) if current else "NEW"
    score = f"{current.score:,}" if current else "NEW"
    acc = current.acc if current else None
    composer = _esc(_song_composer(paths, chart.song_id))
    title = _esc(_song_display_name(paths, chart.song_id, chart.song_title))
    return f"""
<div class="line">
  <div class="song_name"><div class="num"><span name="pvis">{index}</span></div><div class="song"><span name="pvis">{title}{' - ' + composer if composer else ''}</span></div><div class="dif {_esc(chart.rank)}"><span name="pvis">{chart.difficulty:.1f}</span></div></div>
  <div class="ill_box"><img src="{_chart_illustration(paths, chart)}" alt="{title}"></div>
  <div class="info_box"><div class="down">
    <div class="acc"><div class="box-content">{'---' if acc is None else f'{acc:.4f}'}%</div><div class="suggest suggest-kind-{kind}">&gt; {entry.target_acc:.4f}</div></div>
    <div class="score_rating"><div class="score">{_esc(score)}</div><div class="rating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div></div>
  </div></div>
</div>"""


def _phi_suggest_line(paths: PluginPaths, entry: PhiSuggestEntry, index: int) -> str:
    chart = entry.chart
    title = _esc(_song_display_name(paths, chart.song_id, chart.song_title))
    total = max(0, int(entry.total or 0))
    return f"""
<div class="line">
  <div class="song_name"><div class="num"><span name="pvis">{index}</span></div><div class="song"><span name="pvis">{title}</span></div><div class="dif {_esc(chart.rank)}"><span name="pvis">{chart.difficulty:.1f}</span></div></div>
  <div class="ill_box"><img src="{_chart_illustration(paths, chart)}" alt="{title}"></div>
  <div class="info_box"><div class="down">
    <div class="acc"><div class="box-content">AP Count</div><div class="suggest suggest-kind-5">{int(entry.ap_count)} / {total}</div></div>
    <div class="score_rating"><div class="score">{_esc(chart.rank)}</div><div class="rating"><img src="{asset_uri(paths, "html/otherimg/phi.png")}" alt="phi"></div></div>
  </div></div>
</div>"""


def _notice_line(message: str) -> str:
    return f"""
<div class="line">
  <div class="song_name"><div class="num"><span name="pvis">!</span></div><div class="song"><span name="pvis">{_esc(message)}</span></div><div class="dif EZ"><span name="pvis">INFO</span></div></div>
  <div class="info_box"><div class="down"><div class="acc"><div class="box-content">---</div><div class="suggest">---</div></div><div class="score_rating"><div class="score">NO DATA</div></div></div></div>
</div>"""


def _table_player_info(paths: PluginPaths, gameuser: dict[str, Any], date_text: str) -> str:
    avatar = asset_uri(paths, f"html/avatar/{gameuser['avatar']}.png") or asset_uri(paths, "html/avatar/Introduction.png")
    challenge = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    data_img = asset_uri(paths, "html/otherimg/data.png")
    return f"""
<div class="playerInfo">
  <div class="blackBlock clip-box"></div>
  <div class="avatar clip-box"><img src="{avatar}" alt="{_esc(gameuser['avatar'])}"></div>
  <div class="playerId"><p name="pvis">{_esc(gameuser['PlayerId'])}</p></div>
  <div class="rks clip-box"><p>{float(gameuser['rks']):.4f}</p></div>
  <div class="clgBox"><div class="Challenge"><img src="{challenge}" alt="Challenge"><p>{gameuser['ChallengeModeRank']}</p></div></div>
  <div class="date"><p>{_esc(date_text)}</p></div>
  <div class="dataBox clip-box"><img src="{data_img}" alt="data"><p>{_esc(gameuser['data'])}</p></div>
</div>"""


def _table_chart_card(paths: PluginPaths, chart: ChartEntry, record: ScoreRecord | None, *, show_score: bool) -> str:
    score_html = ""
    if show_score:
        if record is None:
            score_html = f'<div class="score"><img src="{asset_uri(paths, "html/otherimg/NEW.png")}" alt="NEW"></div>'
        elif record.acc >= 100:
            score_html = f'<div class="score"><img src="{asset_uri(paths, "html/otherimg/phi.png")}" alt="phi"></div>'
        else:
            score_html = f'<div class="score"><p>{record.acc:.2f}</p></div>'
    return f"""
<div class="song table-{_esc(chart.rank)}">
  <div class="ill clip-box"><img src="{_chart_illustration(paths, chart)}" alt="{_esc(chart.song_title)}">{score_html}</div>
  <div class="rank-box"><div class="rank clip-box"><div class="rankBlock clip-box"></div><p>{_esc(chart.rank)}</p></div></div>
</div>"""


def _table_bucket_rating(charts: list[ChartEntry], record_map: dict[tuple[str, str], ScoreRecord]) -> str:
    values = []
    for chart in charts:
        record = record_map.get((chart.song_id, chart.rank))
        values.append(_rating_rank(_rating_asset(record.rating)) if record else -1)
    if not values:
        return "NEW"
    score = min(values)
    for rating in ("phi", "FC", "V", "S", "A", "B", "C", "F", "NEW"):
        if _rating_rank(rating) == score:
            return rating
    return "NEW"


def _lvscore_rank_box(rank: str, total: int) -> str:
    flag = "true" if total else "false"
    return f'<div class="left-mid-box-{flag}"><div class="rank-left"><p>{_esc(rank)}</p></div>{"<div class=\"rank-right\"><p>" + str(total) + " charts</p><p>" + str(total) + " unlocked</p></div>" if total else ""}</div>'


def _score_rank_card(
    paths: PluginPaths,
    rank: str,
    difficulty: float,
    record: ScoreRecord | None,
    ap_fc_count: dict[str, Any] | None = None,
) -> str:
    if record is None:
        return f"""
<div class="one-stats-box {_esc(rank)}" id="NEW">
  <div class="rank"><p>{_esc(rank)}</p></div>
  <div class="stats-up"><div class="Rating"><img src="{asset_uri(paths, "html/otherimg/NEW.png")}" alt="NEW"></div></div>
  <div class="no_info"><p>Locked</p></div>
</div>"""
    rating = _rating_asset(record.rating)
    suggest, suggest_type = _score_card_suggest(record)
    bottom = _score_ap_fc_line(rank, ap_fc_count) or f'<div class="APCount">Dif: {difficulty:.1f}</div><div class="FCCount">FC: {"YES" if record.fc else "NO"}</div><div class="total">rank:</div><div class="count">{_esc(rank)}</div>'
    return f"""
<div class="one-stats-box {_esc(rank)}" id="{_esc(rating)}">
  <div class="rank"><p>{_esc(rank)}</p></div>
  <div class="stats-up">
    <div class="Rating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div>
    <div class="data_bnpn"><div class="phiN {'active' if rating == 'phi' else ''}"><span>Phi</span><span class="phiN-num">{1 if rating == 'phi' else 0}</span></div><div class="bestN active"><span>Best</span><span class="bestN-num">{record.rks:.2f}</span></div></div>
    <div class="data_score"><p>{record.score:,}</p></div>
  </div>
  <div class="data_mid"><div class="data_rks"><p>{record.rks:.4f}</p></div><div class="data_acc"><p>{record.acc:.4f}%</p></div><div class="suggest suggest-kind-{suggest_type}"><div class="suggest-tip"></div><p>{_esc(suggest)}</p></div></div>
  <div class="data_bottom">{bottom}</div>
</div>"""


def _score_ap_fc_line(rank: str, ap_fc_count: dict[str, Any] | None) -> str:
    data = ap_fc_count.get(rank) if isinstance(ap_fc_count, dict) else None
    if not isinstance(data, dict):
        return ""
    total = _as_int(data.get("total"))
    if total <= 0:
        return ""
    ap = _as_int(data.get("apCount")) / total * 100
    fc = _as_int(data.get("fcCount")) / total * 100
    return f'<div class="APCount">AP: {ap:.2f}%</div><div class="FCCount">FC: {fc:.2f}%</div><div class="total">total:</div><div class="count">{total}</div>'


def _score_card_suggest(record: ScoreRecord) -> tuple[str, str]:
    if record.acc >= 100:
        return "无法推分", "5"
    acc = _suggest_acc(record.rks + 0.001, record.difficulty)
    if acc is None:
        return "100.0000%", "5"
    return f"{acc:.4f}%", _suggest_type(acc)


def _score_difficulty_chip(rank: str, difficulty: float) -> str:
    return f'<div class="a_rank"><div class="a_rank_dif"><p>{difficulty:.1f}</p></div><div class="a_rank_name"><p>{_esc(rank)}</p></div></div>'


def _score_history_row(paths: PluginPaths, record: ScoreRecord) -> str:
    rating = _rating_asset(record.rating)
    return f"""
<div class="oneHistory {_esc(record.rank)}">
  <div class="HistoryDate"><p>{_esc(record.rank)}</p></div>
  <div class="HistoryRating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div>
  <div class="HistoryScore"><p>{record.score:,}</p></div>
  <div class="HistoryAcc"><p>{record.acc:.4f}%</p></div>
  <div class="HistoryRks"><p>{record.rks:.2f}</p></div>
</div>"""


def _chap_song_card(paths: PluginPaths, record: ScoreRecord, index: int) -> str:
    col = index // 10
    row = index % 10
    left = 100 + col * 240 - row * 20
    top = 60 + row * 65
    rating = _rating_asset(record.rating)
    suggest, _suggest_kind = _score_card_suggest(record)
    return f"""
<div class="song song_2" style="left:{left}px;top:{top}px;">
  <div class="common_ill ill"><img src="{_record_illustration(paths, record)}" alt="{_esc(record.song_title)}"></div>
  <div class="info"><div class="rank {_esc(record.rank)}"><div class="rating"><img src="{asset_uri(paths, f"html/otherimg/{rating}.png")}" alt="{_esc(rating)}"></div><div class="dif">{record.difficulty:.1f}</div><div class="score">{record.score:,}</div><div class="acc">{record.acc:.4f}%</div><div class="rks">= {record.rks:.4f}</div><div class="suggest">&gt;&gt; {suggest}</div></div></div>
</div>"""


def _history_change_songs(paths: PluginPaths, change: Any) -> list[str]:
    result = []
    for index, record in getattr(change, "new_phi", []):
        result.append(_history_song(paths, record, new_phi=f"P{index}"))
    for index, record in getattr(change, "new_b27", []):
        result.append(_history_song(paths, record, new_b27=f"B{index}"))
    for record in getattr(change, "exit_phi", []):
        result.append(_history_song(paths, record, exit_phi=True))
    for record in getattr(change, "exit_b27", []):
        result.append(_history_song(paths, record, exit_b27=True))
    return result


def _history_song(
    paths: PluginPaths,
    record: ScoreRecord,
    *,
    new_phi: str = "",
    new_b27: str = "",
    exit_phi: bool = False,
    exit_b27: bool = False,
) -> str:
    tags = []
    if new_phi:
        tags.append(f'<div class="changeTag phiTag clip-box"><img src="{asset_uri(paths, "html/otherimg/phi.png")}" alt="phi"><p>{_esc(new_phi)}</p><div class="changeTagLine clip-box"></div></div>')
    if new_b27:
        tags.append(f'<div class="changeTag b27Tag clip-box"><p>{_esc(new_b27)}</p><div class="changeTagLine clip-box"></div></div>')
    if exit_phi or exit_b27:
        tags.append('<div class="changeTag exitTag clip-box"><p>OUT</p><div class="changeTagLine clip-box"></div></div>')
    return f"""
<div class="s-song">
  <div class="ill-box"><div class="ill clip-box"><img src="{_record_illustration(paths, record)}" alt="{_esc(record.song_title)}"></div><div class="levelKind {_esc(record.rank)}-BKG clip-box"><p>{_esc(record.rank)}</p></div></div>
  <div class="tag-box">{''.join(tags)}</div>
</div>"""


def _history_card(title: str, value: Any, subtitle: str) -> str:
    return f'<div class="card"><div class="card-h">{_esc(title)}</div><div class="card-v">{_esc(value)}</div><div class="card-s">{_esc(subtitle)}</div></div>'


def _history_split(label: str, day: str, delta: str, klass: str) -> str:
    return f'<div class="split"><div class="split-item"><div class="badge {_esc(klass)}">{_esc(label)}</div><div class="split-body"><div class="split-line"><span>日期</span><span>{_esc(day)}</span></div><div class="split-line"><span>增量</span><span class="strong">{_esc(delta)}</span></div></div></div></div>'


def _history_rank_card(title: str, items: list[tuple[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(items[:3], 1):
        rows.append(f'<div class="rankitem"><div class="rankno">#{index}</div><div class="rankmain mono">{_esc(item[0])}</div><div class="rankside">{_esc(item[1])}</div></div>')
    if not rows:
        rows.append('<div class="rankitem"><div class="rankno">#1</div><div class="rankmain">--</div><div class="rankside">--</div></div>')
    return f'<div class="card"><div class="card-h">{_esc(title)}</div><div class="ranklist">{"".join(rows)}</div></div>'


def _randclg_song_card(paths: PluginPaths, chart: ChartEntry, index: int) -> str:
    note_info = _chart_note_info(paths, chart.song_id, chart.rank, chart.combo)
    return f"""
<div class="song-box box-{index}">
  <div class="ill-box"><div class="ill"><img src="{_chart_illustration(paths, chart)}" alt="{_esc(chart.song_title)}"></div><div class="info-box"><div class="song_name"><p name="pvis">{_esc(chart.song_title)}</p></div></div></div>
  <div class="dif"><p>{_esc(chart.rank)}</p><p>{chart.difficulty:.1f}</p></div>
  <div class="notes-box">
    <div class="notes-info tap"><div class="notes_num"><p>{note_info["tap"]}</p></div><div class="notes_title"><p>Tap</p></div></div>
    <div class="notes-info drag"><div class="notes_num"><p>{note_info["drag"]}</p></div><div class="notes_title"><p>Drag</p></div></div>
    <div class="notes-info hold"><div class="notes_num"><p>{note_info["hold"]}</p></div><div class="notes_title"><p>Hold</p></div></div>
    <div class="notes-info flick"><div class="notes_num"><p>{note_info["flick"]}</p></div><div class="notes_title"><p>Flick</p></div></div>
    <div class="notes-info"><div class="notes_num"><p>{note_info["combo"]}</p></div><div class="notes_title"><p>Combo</p></div></div>
  </div>
</div>"""


def _atlas_chart_row(chart: Any) -> str:
    return f"""
<div class="rank">
  <div class="pBox"><p name="pvis">{_esc(chart.rank)}</p><p>{_esc(chart.difficulty_text or (f"{chart.difficulty:.1f}" if chart.difficulty else "?"))}</p></div>
</div>
<div class="rank-box"><div class="charter"><p name="pvis">{_esc(chart.charter)}</p></div><div class="chart-info"><p>{chart.combo or "-"}</p><p></p><p></p><p></p></div></div>"""


def _atlas_info(title: str, value: str) -> str:
    if not value:
        return ""
    return f'<div class="other-box"><div class="title"><p>{_esc(title)}</p></div><div class="dcr"><p>{_esc(value)}</p></div></div>'


def _atlas_comment_box(paths: PluginPaths, comments: dict[str, Any] | None) -> str:
    if not comments:
        return ""
    rows = []
    for item in comments.get("list") or []:
        if isinstance(item, dict):
            rows.append(_atlas_comment_row(paths, item))
    if not rows:
        rows.append('<div class="a_comment"><div class="comment"><p name="pvis">暂无评论</p></div></div>')
    command = comments.get("command") or ""
    return f"""
<div class="comment-box">
  <div class="comment_title"><p>Comments</p><p>{_esc(command)}</p></div>
  {''.join(rows)}
</div>"""


def _atlas_comment_row(paths: PluginPaths, item: dict[str, Any]) -> str:
    avatar = str(item.get("avatar") or "Introduction")
    avatar_uri = asset_uri(paths, f"html/avatar/{avatar}.png") or asset_uri(paths, "html/avatar/Introduction.png")
    player = str(item.get("PlayerId") or item.get("playerId") or item.get("apiUserId") or "UNKNOWN")
    if len(player) > 15:
        player = player[:12] + "..."
    rank = str(item.get("rank") or "IN").upper()
    if rank not in LEVELS:
        rank = "IN"
    challenge = _as_int(item.get("challenge") or item.get("challengeModeRank"))
    challenge_mode = max(0, min(5, challenge // 100))
    challenge_rank = challenge % 100
    score = _as_int(item.get("score"))
    acc = _as_number(item.get("acc"))
    rks = _as_number(item.get("rks") or item.get("rankingScore"))
    comment_id = item.get("thisId") or item.get("id") or "?"
    time = _date_label(item.get("time") or item.get("createdAt") or item.get("updatedAt"))
    content = _safe(str(item.get("comment") or "")).replace("\n", "<br>")
    return f"""
<div class="a_comment">
  <div class="avatar"><img src="{avatar_uri}" alt="{_esc(avatar)}"></div>
  <div class="userInfo">
    <div class="playerId"><p name="pvis">{_esc(player)}</p></div>
    <div class="rks"><p>{rks:.4f}</p></div>
    <div class="score {rank}-BKG"><p>{score}</p></div>
    <div class="acc {rank}-BKG"><p>{acc:.2f}%</p></div>
    <div class="clg_box"><div class="Challenge"><img src="{asset_uri(paths, f"html/otherimg/{challenge_mode}.png")}" alt="{challenge}"><p>{challenge_rank}</p></div></div>
    <div class="time"><p>{_esc(time)}&ensp;ID:{_esc(comment_id)}</p></div>
  </div>
  <div class="comment"><p name="pvis">{content}</p></div>
</div>"""


def _chart_note_info(paths: PluginPaths, song_id: str, rank: str, fallback_combo: int | None) -> dict[str, Any]:
    data = _load_notes_info(paths).get(song_id.removesuffix(".0"))
    rank_data = data.get(rank) if isinstance(data, dict) else None
    totals = rank_data.get("t") if isinstance(rank_data, dict) else None
    if isinstance(totals, list):
        counts = [_as_int(value) for value in totals[:4]]
        while len(counts) < 4:
            counts.append(0)
    else:
        combo = _as_int(fallback_combo)
        counts = [0, 0, 0, 0]
        if combo:
            counts[0] = combo
    combo = sum(counts) or _as_int(fallback_combo)
    distribution = rank_data.get("d") if isinstance(rank_data, dict) else None
    if not isinstance(distribution, list):
        distribution = _fallback_distribution(counts)
    max_time = rank_data.get("m") if isinstance(rank_data, dict) else None
    return {
        "tap": counts[0],
        "drag": counts[1],
        "hold": counts[2],
        "flick": counts[3],
        "combo": combo,
        "distribution": distribution,
        "chart_length": _chart_length(max_time),
    }


def _load_notes_info(paths: PluginPaths) -> dict[str, Any]:
    path = paths.info / "notesInfo.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _fallback_distribution(counts: list[int]) -> list[list[float]]:
    total = sum(counts)
    if total <= 0:
        return [[0, 0, 0, 0, 0] for _ in range(12)]
    row = [round(value / total * 100, 2) for value in counts]
    row.append(100)
    return [row for _ in range(12)]


def _chart_length(value: Any) -> str:
    seconds = _as_int(value)
    if seconds <= 0:
        return "--:--"
    return f"{seconds // 60}:{seconds % 60:02d}"


def _chart_tag_items(tags: dict[str, Any], user_tags: list[str]) -> list[dict[str, Any]]:
    selected = set(user_tags)
    result = []
    for name, value in sorted(tags.items(), key=lambda item: (-_as_int(item[1]), str(item[0]))):
        result.append({"name": str(name), "value": _as_int(value), "selected": str(name) in selected})
    return result


def _chart_distribution_bar(row: Any) -> str:
    values = list(row) if isinstance(row, list) else []
    values = [float(_as_number(value)) for value in values[:5]]
    while len(values) < 5:
        values.append(0.0)
    return f"""
<div class="bar" style="height: {values[4]:.2f}%">
  <div class="bar-item TAP-BKG" style="height: {values[0]:.2f}%"></div>
  <div class="bar-item DRAG-BKG" style="height: {values[1]:.2f}%"></div>
  <div class="bar-item HOLD-BKG" style="height: {values[2]:.2f}%"></div>
  <div class="bar-item FLICK-BKG" style="height: {values[3]:.2f}%"></div>
</div>"""


def _chart_tag_row(item: dict[str, Any], max_value: int) -> str:
    width = _percentage(item["value"], max_value)
    selected = " selected" if item.get("selected") else ""
    return f"""
<div class="tag-row{selected}">
  <p name="pvis">{_esc(item["name"])}</p>
  <div class="tag-meter"><span style="width:{width:.2f}%"></span></div>
  <b>{item["value"]}</b>
</div>"""


def _dot_box() -> str:
    return '<div class="dot left top"></div><div class="dot left bottom"></div><div class="dot right top"></div><div class="dot right bottom"></div>'


def _chart_content_item(title: str, value: str) -> str:
    return f'<div class="content-item"><div class="content-title"><p>{_esc(title)}</p></div><div class="content"><p name="pvis">{_esc(value)}</p></div></div>'


def _chart_note_count(css_class: str, value: int, label: str) -> str:
    return f'<div class="notes-content {_esc(css_class)}"><p>{value}</p><p>{_esc(label)}</p></div>'


def _chart_difficulty_text(chart: Any) -> str:
    return _esc(chart.difficulty_text or (f"{chart.difficulty:.1f}" if chart.difficulty else "?"))


def _as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _song_illustration(paths: PluginPaths, song: Song) -> str:
    path = find_illustration_file(paths, song.id, prefer_low=True)
    if path is not None:
        return _illustration_source(paths, path, song_id=song.id, prefer_low=True)
    if use_remote_illustrations(paths):
        return illustration_url(song.id, prefer_low=True, paths=paths)
    for raw in (song.illustration, song.illustration_big):
        if raw:
            uri = _source_data_uri(paths, raw)
            if uri:
                return uri
            path = paths.other_ill / raw
            uri = _source_data_uri(paths, path)
            if uri:
                return uri
    return asset_uri(paths, "html/otherimg/phigros.png")


def _chart_illustration(paths: PluginPaths, chart: ChartEntry) -> str:
    path = find_illustration_file(paths, chart.song_id, prefer_low=True)
    if path is not None:
        return _illustration_source(paths, path, song_id=chart.song_id, prefer_low=True)
    if use_remote_illustrations(paths):
        return illustration_url(chart.song_id, prefer_low=True, paths=paths)
    return asset_uri(paths, "html/otherimg/phigros.png")


def _random_background_for_entries(paths: PluginPaths, entries: list[ScoreListEntry]) -> str:
    candidates = [entry.record for entry in entries if entry.record is not None]
    if candidates:
        return _random_background_for_records(paths, candidates)
    return _random_background_for_charts(paths, [entry.chart for entry in entries])


def _random_background_for_suggestions(paths: PluginPaths, entries: list[SuggestEntry]) -> str:
    return _random_background_for_charts(paths, [entry.chart for entry in entries])


def _random_background_for_charts(paths: PluginPaths, charts: list[ChartEntry]) -> str:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for chart in charts:
        path = find_background_illustration_file(paths, chart.song_id)
        if path is None and not use_remote_illustrations(paths):
            continue
        if path is not None:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(path)
        elif use_remote_illustrations(paths):
            return background_illustration_url(chart.song_id, paths=paths)
    if candidates:
        selected = random.choice(candidates)
        return _illustration_source(paths, selected, song_id=selected.stem, background=True)
    return _random_background(paths)


def _song_display_name(paths: PluginPaths, song_id: str, fallback: str) -> str:
    return fallback or song_id


def _song_composer(paths: PluginPaths, song_id: str) -> str:
    return ""


def _rating_asset(value: str) -> str:
    text = str(value or "NEW")
    if text == "PHI":
        return "phi"
    if text == "AP":
        return "phi"
    return text


def _rating_rank(value: str) -> int:
    order = {"NEW": -1, "F": 0, "C": 1, "B": 2, "A": 3, "S": 4, "V": 5, "FC": 6, "phi": 7}
    return order.get(_rating_asset(value), -1)


def _dominant_rating_from_counts(counts: dict[str, int]) -> str:
    values = [(rating, count) for rating, count in counts.items() if count]
    if not values:
        return "NEW"
    return max(values, key=lambda item: (item[1], _rating_rank(item[0])))[0]


def _percentage(value: int | float, total: int | float) -> float:
    try:
        total_f = float(total)
        if total_f <= 0:
            return 0.0
        return max(0.0, min(100.0, float(value) / total_f * 100.0))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _b30_record_card(
    paths: PluginPaths,
    record: ScoreRecord,
    number: str,
    *,
    phi: bool,
    b_score: bool = False,
    suggest: tuple[str, str] | None = None,
) -> str:
    rating = asset_uri(paths, f"html/otherimg/{record.rating}.png")
    illustration = _record_illustration(paths, record)
    css_class = "song phi_song" if phi else ("song b_song" if b_score else "song")
    suggest_text, suggest_type = suggest if suggest is not None else ("无法推分", "")
    avg_html = _acc_avg_html(record)
    return f"""
<div class="{css_class}">
  <div class="ill-box">
    <div class="num clip-box"><p name="pvis">{_esc(number)}</p></div>
    <div class="ill clip-box"><img src="{illustration}" alt="ill"></div>
    <div class="rank-{_esc(record.rank)} clip-box">
      <div class="org"><p>{_esc(record.rank)}&ensp;{record.difficulty:.1f}</p></div>
      <div class="rel"><p>{record.rks:.2f}</p></div>
    </div>
  </div>
  <div class="info-{_esc(record.rank)}">
    <div class="songname"><p name="pvis">{_esc(record.song_title)}</p></div>
    <div class="songinfo">
      <div class="Rating"><img src="{rating}" alt="{_esc(record.rating)}"></div>
      <div class="chengji">
        <div class="score"><p>{record.score:,}</p></div>
        <div class="line"></div>
        <div class="acc-box">
          <div class="acc"><p>{record.acc:.2f}%</p></div>
          <div class="suggest suggest-kind-{suggest_type}"><div class="suggest-tip"></div><p>{_esc(suggest_text)}</p></div>
        </div>
      </div>
    </div>
  </div>
  {avg_html}
</div>"""


def _acc_avg_html(record: ScoreRecord) -> str:
    if record.acc_avg is None or not record.acc_kind:
        return ""
    icon = _acc_avg_finished_icon() if record.acc_kind == "Finished" else _acc_avg_arrow_icon()
    return f"""
  <div class="accAvg acc{_esc(record.acc_kind)} clip-box">
    <div class="accAvgLine clip-box"></div>
    {icon}
    <p>Avg: {record.acc_avg:.4f}%</p>
  </div>"""


def _acc_avg_finished_icon() -> str:
    return """
    <svg viewBox="0 0 1024 1024">
      <path d="M892.064 261.888a31.936 31.936 0 0 0-45.216 1.472L421.664 717.248l-220.448-185.216a32 32 0 1 0-41.152 48.992l243.648 204.704a31.872 31.872 0 0 0 20.576 7.488 31.808 31.808 0 0 0 23.36-10.112L893.536 307.136a32 32 0 0 0-1.472-45.248z"></path>
    </svg>"""


def _acc_avg_arrow_icon() -> str:
    return """
    <svg viewBox="0 0 1024 1024">
      <path d="M564.8 465.184l4.192 3.904 274.72 274.752a32 32 0 0 1 0 45.248l-22.624 22.624a32 32 0 0 1-45.248 0l-263.456-263.392-263.424 263.392a32 32 0 0 1-42.24 2.656l-3.008-2.656-22.624-22.624a32 32 0 0 1 0-45.248l274.784-274.752a80 80 0 0 1 108.96-3.904z m0-256l4.192 3.904 274.72 274.752a32 32 0 0 1 0 45.248l-22.624 22.624a32 32 0 0 1-45.248 0l-263.456-263.392-263.424 263.392a32 32 0 0 1-42.24 2.656l-3.008-2.656-22.624-22.624a32 32 0 0 1 0-45.248l274.784-274.752a80 80 0 0 1 108.96-3.904z"></path>
    </svg>"""


def _overflow_html() -> str:
    lines = "".join('<div class="flow_line"></div>' for _ in range(6))
    return f"""
<div class="over_flow">
  <div class="flow_line_box_l">{lines}</div>
  <p><i>OVER FLOW</i></p>
  <div class="flow_line_box_r">{lines}</div>
</div>"""


def _record_suggest(result: Best30Result, record: ScoreRecord, index: int) -> tuple[str, str]:
    if record.acc >= 100 or record.difficulty <= 0:
        return "无法推分", ""
    floor_record = result.records[26] if len(result.records) > 26 else result.records[-1]
    base_rks = record.rks if index <= 26 else floor_record.rks
    target_rks = base_rks + _min_up_rks(result.official_rks) * 30
    acc = _suggest_acc(target_rks, record.difficulty)
    if acc is None:
        last_phi = result.phi_records[-1] if result.phi_records else None
        if last_phi is None or record.rks > last_phi.rks:
            acc = 100.0
        else:
            return "无法推分", ""
    return f"{acc:.2f}%", _suggest_type(acc)


def _record_list_rks(records: list[ScoreRecord]) -> float:
    return sum(record.rks for record in records[:30]) / 30 if records else 0.0


def _record_list_suggest(record: ScoreRecord) -> str:
    if record.rks > 0:
        return f"RKS {record.rks:.2f}"
    return "NO RKS"


def _record_list_suggest_type(record: ScoreRecord) -> str:
    if record.acc >= 100:
        return "5"
    if record.fc:
        return "3"
    if record.score >= 999000:
        return "4"
    return "2"


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


def _min_up_rks(rks: float) -> float:
    value = math.floor(rks * 100) / 100 + 0.005 - rks
    return value + 0.01 if value < 0 else value


def _suggest_acc(target_rks: float, difficulty: float) -> float | None:
    if difficulty <= 0:
        return None
    acc = 45 * math.sqrt(target_rks / difficulty) + 55
    return None if acc >= 100 else acc


def _suggest_type(acc: float) -> str:
    if acc < 98.5:
        return "0"
    if acc < 99:
        return "1"
    if acc < 99.5:
        return "2"
    if acc < 99.7:
        return "3"
    if acc < 99.85:
        return "4"
    return "5"


def _render_reset_css(background: str = "", *, width: int = 1200) -> str:
    background_css = ""
    if background:
        background_css = """
body {
  background-image: none !important;
}
"""
    return f"""
html {{
  margin: 0;
  padding: 0;
  width: {width}px !important;
  min-width: {width}px !important;
  max-width: {width}px !important;
  background: #000;
  overflow-x: hidden !important;
}}
body {{
  margin: 0;
  padding: 0;
  width: {width}px !important;
  min-width: {width}px !important;
  max-width: {width}px !important;
  background: #000 !important;
  overflow-x: hidden !important;
}}
.background {{
  position: absolute !important;
  top: 0 !important;
  left: 0;
  right: auto !important;
  bottom: auto !important;
  width: {width}px !important;
  min-width: {width}px !important;
  max-width: {width}px !important;
  height: 100% !important;
  min-height: 100% !important;
  z-index: 0 !important;
  pointer-events: none !important;
  overflow: hidden !important;
  contain: paint !important;
}}
.background img {{
  width: 100% !important;
  min-width: 100% !important;
  height: 100% !important;
  min-height: 100% !important;
  object-fit: cover !important;
  filter: blur(20px) brightness(50%) !important;
  transform: scale(1.2) !important;
  z-index: 0 !important;
}}
body {{
  position: relative !important;
}}
body > :not(.background) {{
  position: relative;
  z-index: 1;
}}
""" + background_css


def _auto_font_script() -> str:
    return """
function phiIsBiggerThanParent(node, parent) {
  return node.scrollWidth > parent.offsetWidth || node.scrollHeight > parent.offsetHeight;
}
function phiAdjustFontSize() {
  const nodes = document.getElementsByName("pvis");
  for (let i = 0; i < nodes.length; i += 1) {
    const node = nodes[i];
    const parent = node && node.parentElement;
    if (!node || !parent || !phiIsBiggerThanParent(node, parent)) continue;
    let current = Number(window.getComputedStyle(node, null).getPropertyValue("font-size").replace("px", ""));
    let left = 1;
    let right = current;
    while (left < right) {
      const mid = Math.floor((left + right + 1) / 2);
      node.style.fontSize = mid + "px";
      if (phiIsBiggerThanParent(node, parent)) {
        right = mid - 1;
      } else {
        left = mid;
      }
    }
    node.style.fontSize = left + "px";
  }
}
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(phiAdjustFontSize);
}
window.addEventListener("load", phiAdjustFontSize);
window.addEventListener("resize", phiAdjustFontSize);
requestAnimationFrame(phiAdjustFontSize);
"""


def _random_background(paths: PluginPaths) -> str:
    for source in background_source_candidates(paths):
        uri = _source_data_uri(paths, source)
        if uri:
            return uri
    fallback = _other_illustration_data_uri(paths)
    if fallback:
        return fallback
    return asset_uri(paths, "html/otherimg/phigros.png")


def _random_background_for_records(paths: PluginPaths, records: list[ScoreRecord]) -> str:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for record in records:
        path = find_background_illustration_file(paths, record.song_id)
        if path is None and not use_remote_illustrations(paths):
            continue
        if path is not None:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(path)
        elif use_remote_illustrations(paths):
            return background_illustration_url(record.song_id, paths=paths)
    if candidates:
        selected = random.choice(candidates)
        return _illustration_source(paths, selected, song_id=selected.stem, background=True)
    return _random_background(paths)


def _record_illustration(paths: PluginPaths, record: ScoreRecord) -> str:
    path = find_illustration_file(paths, record.song_id, prefer_low=True)
    if path is not None:
        return _illustration_source(paths, path, song_id=record.song_id, prefer_low=True)
    if use_remote_illustrations(paths):
        return illustration_url(record.song_id, prefer_low=True, paths=paths)
    for raw in (getattr(record, "illustration", ""), getattr(record, "illustration_big", "")):
        if not raw:
            continue
        uri = _source_data_uri(paths, raw)
        if uri:
            return uri
        uri = _source_data_uri(paths, paths.other_ill / raw)
        if uri:
            return uri
    return asset_uri(paths, "html/otherimg/phigros.png")


def _css_text(paths: PluginPaths, relative: str) -> str:
    path = paths.resources / relative
    if not path.exists():
        return ""
    css = path.read_text(encoding="utf-8")
    base_dir = path.parent

    def replace_import(match: re.Match[str]) -> str:
        raw_url = match.group(1).strip()
        resolved = (base_dir / raw_url).resolve()
        try:
            relative_path = resolved.relative_to(paths.resources.resolve()).as_posix()
        except ValueError:
            return ""
        return _css_text(paths, relative_path)

    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group(2).strip()
        lowered = raw_url.lower()
        if lowered.startswith(("data:", "#")):
            return match.group(0)
        if lowered.startswith(("http:", "https:", "file:")):
            data_uri = _source_data_uri(paths, raw_url)
            return f'url("{data_uri}")' if data_uri else 'url("")'
        normalized_url = raw_url.replace("\\", "/").lower()
        if normalized_url.endswith("/otherimg/phigros.png") or normalized_url == "../otherimg/phigros.png":
            return 'url("")'
        resolved = (base_dir / raw_url).resolve()
        data_uri = _file_data_uri(resolved)
        return f'url("{data_uri}")' if data_uri else 'url("")'

    css = _CSS_IMPORT_RE.sub(replace_import, css)
    return _CSS_URL_RE.sub(replace_url, css)


def _css_bundle(paths: PluginPaths, relative: str | tuple[str, ...]) -> str:
    if isinstance(relative, tuple):
        return "\n".join(_css_text(paths, f"html/{item}") for item in relative)
    return _css_text(paths, f"html/{relative}")


def _js_text(paths: PluginPaths, relative: str) -> str:
    path = paths.resources / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _file_data_uri(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _source_data_uri(paths: PluginPaths, source: str | Path) -> str:
    if isinstance(source, Path):
        remote_url = online_url_for_local_path(paths, source) if use_remote_illustrations(paths) else None
        if remote_url:
            return remote_url
        return _file_data_uri(source)
    text = str(source or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith("data:image/"):
        return text
    if lowered.startswith("base64://"):
        return f"data:image/png;base64,{text[len('base64://'):]}"
    if lowered.startswith(("http://", "https://")):
        if use_remote_illustrations(paths) and is_online_illustration_url(text):
            return text
        return _remote_image_data_uri(paths, text)
    if lowered.startswith("file://"):
        parsed = urlparse(text)
        file_path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", file_path):
            file_path = file_path[1:]
        return _file_data_uri(Path(file_path))
    return _file_data_uri(Path(text))


def _illustration_source(
    paths: PluginPaths,
    path: Path | None,
    *,
    song_id: str = "",
    prefer_low: bool = False,
    background: bool = False,
) -> str:
    if use_remote_illustrations(paths):
        if background and song_id:
            return background_illustration_url(song_id, paths=paths)
        if path is not None:
            url = online_url_for_local_path(paths, path)
            if url:
                return url
        if song_id:
            return background_illustration_url(song_id, paths=paths) if background else illustration_url(song_id, prefer_low=prefer_low, paths=paths)
    return _file_data_uri(path) if path is not None else ""


def _remote_image_data_uri(paths: PluginPaths, url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return ""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_dir = paths.cache / "remote_backgrounds"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        cached = cache_dir / f"{digest}{suffix}"
        if cached.exists() and cached.is_file():
            return _file_data_uri(cached)
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
                "User-Agent": "astrbot-phi-plugin/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            payload = response.read(8 * 1024 * 1024)
    except Exception:
        return ""
    if not payload or not content_type.startswith("image/"):
        return ""
    suffix = mimetypes.guess_extension(content_type) or ".png"
    cached = cache_dir / f"{digest}{suffix}"
    cached.write_bytes(payload)
    return _file_data_uri(cached)


def _other_illustration_data_uri(paths: PluginPaths) -> str:
    if not paths.other_ill.exists() or not paths.other_ill.is_dir():
        return ""
    for path in sorted(paths.other_ill.iterdir()):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            uri = _file_data_uri(path)
            if uri:
                return uri
    return ""


def _level_stats(records: Iterable[ScoreRecord]) -> list[dict[str, Any]]:
    by_level: dict[str, list[ScoreRecord]] = {level: [] for level in LEVELS}
    for record in records:
        if record.rank in by_level:
            by_level[record.rank].append(record)
    result = []
    for level in LEVELS:
        level_records = by_level[level]
        result.append({
            "title": level,
            "cleared": len(level_records),
            "fc": sum(1 for record in level_records if record.fc),
            "phi": sum(1 for record in level_records if record.rating == "phi"),
        })
    return result


def _gameuser(snapshot: SaveSnapshot) -> dict[str, Any]:
    raw_user = snapshot.raw.get("gameuser") if isinstance(snapshot.raw.get("gameuser"), dict) else {}
    challenge = _as_int(snapshot.challenge_mode_rank)
    money = extract_money(snapshot.raw) or [0, 0, 0, 0, 0]
    return {
        "avatar": str(raw_user.get("avatar") or "Introduction"),
        "PlayerId": snapshot.player_id or snapshot.player_name or "UNKNOWN",
        "rks": snapshot.ranking_score,
        "ChallengeMode": max(0, min(5, challenge // 100)),
        "ChallengeModeRank": challenge % 100,
        "data": _format_money(money),
    }


def _format_money(money: list[int]) -> str:
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    return " ".join(f"{value}{unit}" for value, unit in reversed(list(zip(money, units))) if value) or "0KiB"


def _command_text(value: str, cmd_head: str) -> str:
    return _safe(value.replace("/", f"{cmd_head} ").replace("杠", f"{cmd_head} "))


def _safe(value: str) -> str:
    return html.escape(value, quote=True).replace("&lt;br&gt;", "<br>")


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
