from __future__ import annotations

import re

from ._rendering import render_original_html
from .common import CommandContext, CommandResult
from ..models import LEVELS, Song
from ..render import original
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"chart"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    song_query, rank = _parse_song_rank(args)
    if not song_query:
        return CommandResult.text(render.render_need_query("chart"))
    song = ctx.searcher.best(song_query)
    if not song:
        return CommandResult.text(render.render_search(song_query, []))
    if rank not in song.charts:
        return CommandResult.text(_missing_rank(song, rank))

    tags = await _fetch_tags(ctx, song, rank)
    user_tags = await _fetch_user_tags(ctx, user_id, song, rank)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(
            ctx,
            original.chart_html(ctx.paths, song, rank, tags=tags, user_tags=user_tags),
            "chart",
        )
        return CommandResult.image(path)
    return CommandResult.text(_render_chart_text(song, rank, tags))


async def _fetch_tags(ctx: CommandContext, song: Song, rank: str) -> dict[str, object]:
    try:
        return await ctx.client.fetch_chart_tags(song.id, rank)
    except SaveNotAvailable:
        return {}


async def _fetch_user_tags(ctx: CommandContext, user_id: str, song: Song, rank: str) -> list[str]:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return []
    try:
        return await ctx.client.fetch_chart_user_votes(user_id, token=token, api_id=api_id, song_id=song.id, rank=rank)
    except SaveNotAvailable:
        return []


def _parse_song_rank(args: str) -> tuple[str, str]:
    text = args.strip()
    match = re.search(r"\b(EZ|HD|IN|AT)\b", text, flags=re.IGNORECASE)
    if not match:
        return text, "IN"
    rank = match.group(1).upper()
    song_query = (text[:match.start()] + text[match.end():]).strip()
    return song_query, rank if rank in LEVELS else "IN"


def _missing_rank(song: Song, rank: str) -> str:
    ranks = " / ".join(chart.rank for chart in song.display_charts())
    return f"「{song.title}」没有 {rank} 谱面。可用难度：{ranks or '暂无'}"


def _render_chart_text(song: Song, rank: str, tags: dict[str, object]) -> str:
    chart = song.charts[rank]
    lines = [
        f"{song.title} - {rank}",
        f"定数: {chart.difficulty_text or (f'{chart.difficulty:.1f}' if chart.difficulty else '?')}",
        f"谱师: {chart.charter or '-'}",
        f"Combo: {chart.combo or '-'}",
    ]
    if tags:
        lines.append("谱面标签:")
        for tag, value in sorted(tags.items(), key=lambda item: (-_as_int(item[1]), str(item[0]))):
            lines.append(f"- {tag}: {value}")
    return "\n".join(lines)


def _as_int(value: object) -> int:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
