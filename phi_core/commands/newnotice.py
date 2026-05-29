from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data import load_notice
from ..render import text as render

ALIASES = {"newnotice"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return CommandResult.text(render.render_notice(load_notice(ctx.paths.info)))
