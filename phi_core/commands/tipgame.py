from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_tipgame

ALIASES = {"tipgame", "提示猜曲"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_tipgame(ctx, user_id, args)
