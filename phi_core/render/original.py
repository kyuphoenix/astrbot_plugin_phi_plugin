from __future__ import annotations

import html
import json
import base64
import hashlib
import mimetypes
import math
import random
import re
import urllib.request
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from ..data.illustrations import background_source_candidates, find_background_illustration_file, find_illustration_file
from ..data.resources import latest_version_log, load_version_log
from ..models import Best30Result, LEVELS, SaveSnapshot, ScoreRecord
from ..paths import PluginPaths
from ..query.progress import extract_modified_datetime, extract_money, format_datetime

_CSS_URL_RE = re.compile(r"url\((['\"]?)([^)'\"]+)\1\)")


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
  <meta name="viewport" content="width=1200">
  <link rel="shortcut icon" href="#">
  <style>{_css_text(paths, "html/common/common.css")}</style>
  <style>{_css_text(paths, f"html/{css_rel}")}</style>
  <style>{_render_reset_css(page_background if theme != "star" else "")}</style>
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


def _render_reset_css(background: str = "") -> str:
    background_css = ""
    if background:
        safe_background = background.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")
        background_css = f"""
html::before {{
  content: "";
  position: fixed;
  inset: -40px;
  background-image: url("{safe_background}");
  background-position: center;
  background-size: cover;
  background-repeat: no-repeat;
  filter: blur(20px) brightness(50%);
  transform: scale(1.08);
  z-index: 0;
  pointer-events: none;
}}
body {{
  background-image: none !important;
}}
"""
    return """
html {
  margin: 0;
  padding: 0;
  width: 1200px !important;
  min-width: 1200px !important;
  max-width: 1200px !important;
  background: #000;
  overflow-x: hidden !important;
}
body {
  margin: 0;
  padding: 0;
  width: 1200px !important;
  min-width: 1200px !important;
  max-width: 1200px !important;
  background: #000 !important;
  overflow-x: hidden !important;
}
.background {
  position: fixed !important;
  top: 0 !important;
  left: 0;
  right: auto !important;
  bottom: auto !important;
  width: 1200px !important;
  min-width: 1200px !important;
  max-width: 1200px !important;
  height: 100vh !important;
  min-height: 100vh !important;
  z-index: 0 !important;
  pointer-events: none !important;
}
.background img {
  width: 100% !important;
  min-width: 100% !important;
  height: 100% !important;
  min-height: 100% !important;
  object-fit: cover !important;
  filter: blur(20px) brightness(50%) !important;
  transform: scale(1.2) !important;
  z-index: 0 !important;
}
body > :not(.background) {
  position: relative;
  z-index: 1;
}
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
        if path is None:
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(path)
    if candidates:
        return _file_data_uri(random.choice(candidates))
    return _random_background(paths)


def _record_illustration(paths: PluginPaths, record: ScoreRecord) -> str:
    path = find_illustration_file(paths, record.song_id, prefer_low=True)
    if path is not None:
        return _file_data_uri(path)
    return asset_uri(paths, "html/otherimg/phigros.png")


def _css_text(paths: PluginPaths, relative: str) -> str:
    path = paths.resources / relative
    if not path.exists():
        return ""
    css = path.read_text(encoding="utf-8")
    base_dir = path.parent

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

    return _CSS_URL_RE.sub(replace_url, css)


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
        return _remote_image_data_uri(paths, text)
    if lowered.startswith("file://"):
        parsed = urlparse(text)
        file_path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", file_path):
            file_path = file_path[1:]
        return _file_data_uri(Path(file_path))
    return _file_data_uri(Path(text))


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
