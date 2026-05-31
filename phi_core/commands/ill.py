from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"ill", "曲绘"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("ill"))
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    path = ctx.find_illustration(song)
    if path:
        if ctx.config.render_mode == "image" and ctx.html_render is not None:
            rendered = await render_jinja_template(
                ctx,
                "ill/ill",
                jinja_adapter.ill_data(ctx.paths, path, song.illustrator),
                "ill",
            )
            return CommandResult.image(rendered)
        return CommandResult.image(path)
    return CommandResult.text(render.render_missing_illustration(song))
