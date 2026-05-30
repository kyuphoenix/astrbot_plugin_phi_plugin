from __future__ import annotations

from ._history_common import load_merged_history
from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import summarize_user
from ..render import original
from ..render import text as render

ALIASES = {"info"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    history = await load_merged_history(ctx, user_id, ["data", "rks", "scoreHistory", "challengeModeRank"])
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(
            ctx,
            original.info_html(
                ctx.paths,
                summarize_user(snapshot, ctx.catalog),
                snapshot=snapshot,
                history=history,
                catalog=ctx.catalog,
            ),
            "info",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_user_info(summarize_user(snapshot, ctx.catalog)))
