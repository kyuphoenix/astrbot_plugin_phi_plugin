from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import suggest_entries
from ..render import original
from ..render import text as render

ALIASES = {"suggest", "\u63a8\u5206", "\u63a8\u5206\u5efa\u8bae"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    entries = suggest_entries(snapshot, ctx.catalog)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.suggest_html(ctx.paths, entries), "suggest")
        return CommandResult.image(path)
    return CommandResult.text(render.render_suggest(entries))
