from __future__ import annotations

from .common import CommandContext, CommandResult
from ._bind_common import bind_account

ALIASES = {"gbbind", "gb绑定"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await bind_account(ctx, user_id, args, is_global=True)
