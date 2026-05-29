from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"song", "曲"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("song"))
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    return CommandResult.text(render.render_song(song))
