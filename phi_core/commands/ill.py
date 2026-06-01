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
    source = ctx.illustration_source(song, prefer_low=False)
    if source:
        if ctx.config.render_mode == "image" and ctx.html_render is not None:
            rendered = await render_jinja_template(
                ctx,
                "ill/ill",
                jinja_adapter.ill_data(ctx.paths, source, song.illustrator),
                "ill",
                width=2048,
                height=1080,
            )
            return CommandResult.image(rendered)
        return CommandResult.image(source)
    return CommandResult.text(render.render_missing_illustration(song))
