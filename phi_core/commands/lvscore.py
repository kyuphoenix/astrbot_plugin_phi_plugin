from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import parse_score_filter, summarize_level_scores
from ..render import text as render

ALIASES = {"lvscore", "lvsco", "scolv"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    score_filter = parse_score_filter(args, max_difficulty=_max_difficulty(ctx))
    return CommandResult.text(render.render_level_score(summarize_level_scores(snapshot, ctx.catalog, score_filter)))


def _max_difficulty(ctx: CommandContext) -> float:
    return max((chart.difficulty for song in ctx.catalog.all_songs() for chart in song.charts.values() if chart.difficulty), default=18.0)
