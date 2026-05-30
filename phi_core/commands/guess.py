from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_guess

ALIASES = {"guess", "猜曲绘"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_guess(ctx, user_id, args)
