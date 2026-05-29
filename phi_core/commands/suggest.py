from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import suggest_entries
from ..render import text as render

ALIASES = {"suggest", "推分", "推分建议"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    return CommandResult.text(render.render_suggest(suggest_entries(snapshot, ctx.catalog)))
