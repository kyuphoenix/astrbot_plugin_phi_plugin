from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..models import LEVELS, Song
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"tag"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    song_query, rank = _parse_song_rank(args)
    if not song_query:
        return CommandResult.text("格式：phi tag <曲名> [EZ|HD|IN|AT]")
    song = ctx.searcher.best(song_query)
    if not song:
        return CommandResult.text(render.render_search(song_query, []))
    if rank not in song.charts:
        return CommandResult.text(_missing_rank(song, rank))
    try:
        tag_data = await ctx.client.fetch_chart_tags(song.id, rank)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"获取谱面标签失败：{exc}")
    return CommandResult.text(render.render_chart_tags(song, rank, tag_data))


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
