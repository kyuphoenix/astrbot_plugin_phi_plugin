from __future__ import annotations

import html
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..models import Best30Result, LEVELS, SaveSnapshot, ScoreRecord
from ..paths import PluginPaths
from ..query.progress import extract_modified_datetime, extract_money, format_datetime


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
    body.append('<canvas id="stars"></canvas><script>themeStar();</script>')
    return original_page(paths, "help/help.css", "\n".join(body), theme="star")


def b30_html(paths: PluginPaths, result: Best30Result, snapshot: SaveSnapshot) -> str:
    records = result.records
    phi_records = [record for record in records if record.acc >= 100][:3]
    b27_records = [record for record in records if record not in phi_records][:27]
    stats = _level_stats(records)
    gameuser = _gameuser(snapshot)
    date_text = format_datetime(extract_modified_datetime(snapshot.raw))
    background = _record_illustration(paths, records[0]) if records else asset_uri(paths, "html/otherimg/phigros.png")

    body: list[str] = [_b30_title(paths, gameuser, stats, date_text)]
    body.append('<div class="b19">')
    for index, record in enumerate(phi_records, 1):
        body.append(_b30_record_card(paths, record, f"P{index}", phi=True))
    for index, record in enumerate(b27_records, 1):
        if index == 28:
            body.append('<div class="over_flow"><p><i>OVER FLOW</i></p></div>')
        body.append(_b30_record_card(paths, record, str(index), phi=False))
    body.append("</div>")
    body.append('<canvas id="stars"></canvas><script>themeStar();</script>')
    return original_page(paths, "b19/b19.css", "\n".join(body), theme="star", background=background)


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


def original_page(paths: PluginPaths, css_rel: str, body: str, *, theme: str = "star", background: str = "") -> str:
    common_css = asset_uri(paths, "html/common/common.css")
    css = asset_uri(paths, f"html/{css_rel}")
    star_js = asset_uri(paths, "html/common/theme/star/star.js")
    star1 = asset_uri(paths, "html/otherimg/Star1.png")
    star2 = asset_uri(paths, "html/otherimg/Star2.png")
    fallback = asset_uri(paths, "html/otherimg/phigros.png")
    background_html = f"""
    <div class="background">
      {'<img src="' + star1 + '" alt="曲绘-模糊"><img src="' + star2 + '" alt="曲绘-模糊" style="min-height:0;width:100%;height:auto;bottom:0;filter:none;">' if theme == "star" else '<img src="' + (background or fallback) + '" alt="曲绘-模糊">'}
    </div>
    """
    return f"""<!DOCTYPE html>
<html lang="zh-cn">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width">
  <link rel="shortcut icon" href="#">
  <link rel="stylesheet" type="text/css" href="{common_css}">
  <link rel="stylesheet" type="text/css" href="{css}">
  <title>phi-plugin</title>
</head>
<body class="elem-hydro default-mode">
  {background_html}
  <script>var _res_path = "{asset_uri(paths, '')}";</script>
  <script src="{star_js}"></script>
  {body}
</body>
</html>"""


def asset_uri(paths: PluginPaths, relative: str) -> str:
    base = paths.resources
    if relative:
        base = base / relative
    return base.resolve().as_uri()


def _b30_title(paths: PluginPaths, gameuser: dict[str, Any], stats: list[dict[str, Any]], date_text: str) -> str:
    avatar_path = paths.resources / "html" / "avatar" / f"{gameuser['avatar']}.png"
    avatar = avatar_path.resolve().as_uri() if avatar_path.exists() else asset_uri(paths, "html/avatar/Introduction.png")
    challenge = asset_uri(paths, f"html/otherimg/{gameuser['ChallengeMode']}.png")
    data_img = asset_uri(paths, "html/otherimg/data.png")
    stat_headers = "".join(f'<div class="poz"><p>{_esc(item["title"])}</p></div>' for item in stats)
    cleared = "".join(f'<div class="poz"><p>{item["cleared"]}</p></div>' for item in stats)
    fc = "".join(f'<div class="poz"><p>{item["fc"]}</p></div>' for item in stats)
    phi = "".join(f'<div class="poz"><p>{item["phi"]}</p></div>' for item in stats)
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


def _b30_record_card(paths: PluginPaths, record: ScoreRecord, number: str, *, phi: bool) -> str:
    rating = asset_uri(paths, f"html/otherimg/{record.rating}.png")
    illustration = _record_illustration(paths, record)
    css_class = "song phi_song" if phi else "song"
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
          <div class="suggest suggest-kind-Finished"><p>RKS {record.rks:.4f}</p></div>
        </div>
      </div>
    </div>
  </div>
</div>"""


def _record_illustration(paths: PluginPaths, record: ScoreRecord) -> str:
    base_id = record.song_id.removesuffix(".0")
    candidates = [
        paths.downloaded_original_ill / "ill" / f"{base_id}.png",
        paths.downloaded_original_ill / f"{base_id}.png",
        paths.original_ill / "ill" / f"{base_id}.png",
        paths.original_ill / f"{base_id}.png",
    ]
    for path in candidates:
        if path.exists():
            return path.resolve().as_uri()
    return asset_uri(paths, "html/otherimg/phigros.png")


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
