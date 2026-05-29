from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import summarize_user
from ..render import text as render

ALIASES = {"info"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    return CommandResult.text(render.render_user_info(summarize_user(snapshot, ctx.catalog)))
