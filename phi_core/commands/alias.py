from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"alias"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args.strip():
        return CommandResult.text(render.render_need_query("alias"))
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    return CommandResult.text(render.render_alias(song))
