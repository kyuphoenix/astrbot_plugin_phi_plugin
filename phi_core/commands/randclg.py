from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import random_challenge
from ..render import text as render

ALIASES = {"randclg"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    result = random_challenge(ctx.catalog, args)
    if result is None:
        return CommandResult.text("未找到符合条件的随机课题。可以试试：phi randclg 30-45")
    target, charts = result
    return CommandResult.text(render.render_random_challenge(target, charts))
