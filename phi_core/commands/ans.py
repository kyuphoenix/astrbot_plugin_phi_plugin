from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_ans

ALIASES = {"ans", "答案", "结束"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_ans(ctx, user_id, args)
