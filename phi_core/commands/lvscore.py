from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import parse_score_filter, summarize_level_scores
from ..render import original
from ..render import text as render

ALIASES = {"lvscore", "lvsco", "scolv"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    score_filter = parse_score_filter(args, max_difficulty=_max_difficulty(ctx))
    summary = summarize_level_scores(snapshot, ctx.catalog, score_filter)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.lvscore_html(ctx.paths, summary, snapshot), "lvscore")
        return CommandResult.image(path)
    return CommandResult.text(render.render_level_score(summary))


def _max_difficulty(ctx: CommandContext) -> float:
    return max((chart.difficulty for song in ctx.catalog.all_songs() for chart in song.charts.values() if chart.difficulty), default=18.0)
