from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data import random_tip
from ..render import text as render

ALIASES = {"tips"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return CommandResult.text(render.render_tip(random_tip(ctx.paths.info)))
