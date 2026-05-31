from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ._rendering import render_jinja_template
from .common import CommandContext, CommandResult
from ..render import jinja_adapter

ALIASES = {"jrrp", "今日人品"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    now = _now_utc8()
    today = now.strftime("%Y-%m-%d")
    cached = ctx.store.get_jrrp_cache(user_id, today)
    if cached is None:
        cached = _make_jrrp(ctx.paths.info, rng=random.Random())
        ctx.store.save_jrrp_cache(user_id, today, cached)
    data = _panel_data(ctx, cached, now=now)
    if ctx.config.render_mode == "image":
        path = await render_jinja_template(ctx, "jrrp/jrrp", jinja_adapter.jrrp_data(ctx.paths, data), "jrrp", width=2048, height=1080)
        return CommandResult.image(path)
    return CommandResult.text(_text_result(data))


def _make_jrrp(info_dir: Path, *, rng: random.Random) -> list[Any]:
    sentences = _load_sentences(info_dir)
    words = _load_words(info_dir)
    sentence_index = rng.randrange(len(sentences)) if sentences else 0
    value: list[Any] = [round(_ease_out_cubic(rng.random()) * 100), sentence_index]
    good = list(words.get("good", []))
    bad = list(words.get("bad", []))
    common = list(words.get("common", []))
    value.extend(_pick_words(rng, good, common, 4))
    value.extend(_pick_words(rng, bad, common, 4))
    return value


def _panel_data(ctx: CommandContext, value: list[Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now_utc8()
    lucky = _as_int(value[0] if value else 0)
    sentences = _load_sentences(ctx.paths.info)
    sentence_index = _as_int(value[1] if len(value) > 1 else 0)
    sentence = sentences[sentence_index % len(sentences)] if sentences else {"hitokoto": "今天也要好好打歌。", "from": "Phi"}
    return {
        "bkg": ctx.paths.other_ill / "ShineAfter.ADeanJocularACE.0.png",
        "lucky": lucky,
        "luckRank": 5 if lucky == 100 else 4 if lucky >= 80 else 3 if lucky >= 60 else 2 if lucky >= 40 else 1 if lucky >= 20 else 0,
        "year": now.year,
        "month": f"{now.month:02d}",
        "day": f"{now.day:02d}",
        "sentence": sentence,
        "good": [str(item) for item in value[2:6]],
        "bad": [str(item) for item in value[6:10]],
    }


def _pick_words(rng: random.Random, primary: list[str], common: list[str], count: int) -> list[str]:
    result: list[str] = []
    for _ in range(count):
        pool_len = len(primary) + len(common)
        if pool_len <= 0:
            break
        index = rng.randrange(pool_len)
        if index < len(primary):
            result.append(primary.pop(index))
        else:
            result.append(common.pop(index - len(primary)))
    return result


def _load_words(info_dir: Path) -> dict[str, list[str]]:
    path = info_dir / "jrrp.json"
    if not path.exists():
        return {"good": ["推分"], "bad": ["熬夜"], "common": ["查分", "打歌", "收歌", "摸鱼"]}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        data = {}
    result: dict[str, list[str]] = {}
    for key in ("good", "bad", "common"):
        raw = data.get(key) if isinstance(data, dict) else []
        result[key] = [str(item) for item in raw] if isinstance(raw, list) else []
    return result


def _load_sentences(info_dir: Path) -> list[dict[str, Any]]:
    path = info_dir / "sentences.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _text_result(data: dict[str, Any]) -> str:
    sentence = data.get("sentence") if isinstance(data.get("sentence"), dict) else {}
    return "\n".join(
        [
            f"今日人品：{data['lucky']}",
            "宜：" + "、".join(data.get("good", [])),
            "忌：" + "、".join(data.get("bad", [])),
            f"{sentence.get('hitokoto', '')} ——「{sentence.get('from', '')}」",
        ]
    )


def _ease_out_cubic(x: float) -> float:
    return 1 - math.pow(1 - x, 3)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _now_utc8() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))
