from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..render import original
from ..render import text as render

ALIASES = {"song", "\u66f2"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("song"))
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.song_html(ctx.paths, song), "song")
        return CommandResult.image(path)
    return CommandResult.text(render.render_song(song))
