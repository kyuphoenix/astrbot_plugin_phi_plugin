from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..query import random_challenge
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"randclg"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    result = random_challenge(ctx.catalog, args)
    if result is None:
        return CommandResult.text("\u672a\u627e\u5230\u7b26\u5408\u6761\u4ef6\u7684\u968f\u673a\u8bfe\u9898\u3002\u53ef\u4ee5\u8bd5\u8bd5\uff1aphi randclg 30-45")
    target, charts = result
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_jinja_template(ctx, "clg/clg", jinja_adapter.clg_data(ctx.paths, target, charts), "randclg")
        return CommandResult.image(path)
    return CommandResult.text(render.render_random_challenge(target, charts))
