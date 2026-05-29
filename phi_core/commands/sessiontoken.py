from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"sessiontoken", "token", "tk"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return CommandResult.text(render.render_session_token(
        ctx.store.get_token(user_id),
        ctx.store.get_api_id(user_id),
    ))
