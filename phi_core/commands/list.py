from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..query import filter_score_entries, parse_score_filter
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"list"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    score_filter = parse_score_filter(args, max_difficulty=_max_difficulty(ctx))
    entries = filter_score_entries(snapshot, ctx.catalog, score_filter)
    if len(entries) > ctx.config.list_score_max_num:
        return CommandResult.text(
            f"谱面数量过多({len(entries)})大于设置的最大值({ctx.config.list_score_max_num})，请缩小搜索范围QAQ！"
        )
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        request_lines = score_filter.original_request_lines()
        title = "Score List | " + " / ".join(request_lines)
        path = await render_jinja_template(
            ctx,
            "list/list",
            jinja_adapter.list_data(ctx.paths, entries, title=title, limit=ctx.config.list_score_max_num),
            "list",
        )
        return CommandResult.image(path)
    return CommandResult.text(
        render.render_score_list(entries, score_filter.original_request_lines(), limit=ctx.config.list_score_max_num)
    )


def _max_difficulty(ctx: CommandContext) -> float:
    return max((chart.difficulty for song in ctx.catalog.all_songs() for chart in song.charts.values() if chart.difficulty), default=18.0)
