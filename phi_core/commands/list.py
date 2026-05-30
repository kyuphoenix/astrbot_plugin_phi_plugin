from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import filter_score_entries, parse_score_filter
from ..render import original
from ..render import text as render

ALIASES = {"list"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    score_filter = parse_score_filter(args, max_difficulty=_max_difficulty(ctx))
    entries = filter_score_entries(snapshot, ctx.catalog, score_filter)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        title = "Score List | " + " / ".join(score_filter.request_lines())
        path = await render_original_html(ctx, original.list_html(ctx.paths, entries, title=title), "list")
        return CommandResult.image(path)
    return CommandResult.text(render.render_score_list(entries, score_filter.request_lines()))


def _max_difficulty(ctx: CommandContext) -> float:
    return max((chart.difficulty for song in ctx.catalog.all_songs() for chart in song.charts.values() if chart.difficulty), default=18.0)
