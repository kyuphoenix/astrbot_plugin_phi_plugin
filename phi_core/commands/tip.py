from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_tip

ALIASES = {"tip", "提示"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_tip(ctx, user_id, args)
