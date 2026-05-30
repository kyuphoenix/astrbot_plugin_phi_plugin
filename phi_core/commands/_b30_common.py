from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import compute_b30
from ..render import original
from ..render import panel
from ..render import text as render


async def render_best30(ctx: CommandContext, user_id: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    limit = max(33, ctx.config.max_b30)
    result = compute_b30(snapshot, ctx.catalog, limit=limit)
    if ctx.config.render_mode == "image":
        path = await panel.render_html(
            ctx.config,
            ctx.paths,
            original.b30_html(ctx.paths, result, snapshot),
            "b30",
            html_render=ctx.html_render,
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_b30(result, limit=limit))
