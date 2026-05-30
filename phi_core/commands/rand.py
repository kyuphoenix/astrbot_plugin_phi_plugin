from __future__ import annotations

import random

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..render import original
from ..render import text as render

ALIASES = {"rand", "random", "\u968f\u673a"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    song = random.choice(ctx.catalog.all_songs())
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.rand_html(ctx.paths, song), "rand")
        return CommandResult.image(path)
    return CommandResult.text(render.render_random(song))
