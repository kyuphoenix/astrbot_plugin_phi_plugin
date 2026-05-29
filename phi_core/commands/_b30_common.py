from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import compute_b30
from ..render import text as render


def render_best30(ctx: CommandContext, user_id: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    result = compute_b30(snapshot, ctx.catalog, limit=ctx.config.max_b30)
    return CommandResult.text(render.render_b30(result, limit=ctx.config.max_b30))
