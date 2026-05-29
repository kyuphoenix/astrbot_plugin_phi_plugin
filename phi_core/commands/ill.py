from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"ill", "曲绘"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("ill"))
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    path = ctx.find_illustration(song)
    if path:
        return CommandResult.image(path)
    return CommandResult.text(render.render_missing_illustration(song))
