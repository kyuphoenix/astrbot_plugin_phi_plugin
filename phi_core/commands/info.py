from __future__ import annotations

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
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(
            ctx,
            original.info_html(
                ctx.paths,
                summarize_user(snapshot, ctx.catalog),
                snapshot=snapshot,
                history=ctx.store.load_history(user_id),
                catalog=ctx.catalog,
            ),
            "info",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_user_info(summarize_user(snapshot, ctx.catalog)))
