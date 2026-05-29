from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"search", "查找", "检索"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("search"))
    return CommandResult.text(render.render_search(args, ctx.searcher.search(args, limit=10)))
