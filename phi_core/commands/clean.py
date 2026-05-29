from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"clean"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return CommandResult.text(render.render_unbind(ctx.store.clean(user_id)))
