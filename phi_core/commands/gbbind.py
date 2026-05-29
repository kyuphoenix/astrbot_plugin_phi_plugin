from __future__ import annotations

from .common import CommandContext, CommandResult
from ._bind_common import bind_token

ALIASES = {"gbbind", "gb绑定"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return bind_token(ctx, user_id, args)
