from __future__ import annotations

import random

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..models import ChartEntry, LEVELS, Song
from ..query import all_chart_entries, parse_range
from ..query.filters import parse_levels
from ..render import jinja_adapter

ALIASES = {"rand", "random", "\u968f\u673a"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    result = _random_chart(ctx, args)
    if result is None:
        return CommandResult.text(_not_found_text(ctx, args))
    song, chart = result
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_jinja_template(ctx, "rand/rand", jinja_adapter.rand_data(ctx.paths, song, chart), "rand", width=2048, height=1080)
        return CommandResult.image(path)
    return CommandResult.text(_render_random_chart(song, chart))


def _random_chart(ctx: CommandContext, args: str, *, rng: random.Random | None = None) -> tuple[Song, ChartEntry] | None:
    rng = rng or random.Random()
    entries = all_chart_entries(ctx.catalog)
    max_difficulty = max((entry.difficulty for entry in entries), default=18.0)
    value_range = parse_range(args, default=(0.0, max_difficulty), max_value=max_difficulty, int_bucket=True)
    levels = parse_levels(args)
    candidates = [
        entry
        for entry in entries
        if entry.rank in levels and value_range.contains(entry.difficulty)
    ]
    if not candidates:
        return None
    chart = rng.choice(candidates)
    song = ctx.catalog.get(chart.song_id)
    if song is None:
        return None
    return song, chart


def _render_random_chart(song: Song, chart: ChartEntry) -> str:
    combo = f" / {chart.combo} notes" if chart.combo else ""
    return "\n".join([
        "随机谱面：",
        f"{chart.rank} {song.title}",
        f"定数: {chart.difficulty:.1f}{combo}",
        f"ID: {song.id}",
        f"BPM: {song.bpm or '-'}",
        f"曲师: {song.composer or '-'}",
    ])


def _not_found_text(ctx: CommandContext, args: str) -> str:
    entries = all_chart_entries(ctx.catalog)
    max_difficulty = max((entry.difficulty for entry in entries), default=18.0)
    value_range = parse_range(args, default=(0.0, max_difficulty), max_value=max_difficulty, int_bucket=True)
    levels = parse_levels(args)
    level_text = " ".join(level for level in LEVELS if level in levels)
    return f"未找到 {value_range.label()} 的 {level_text} 谱面QAQ!"
