from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_open

ALIASES = {"open", "揭开", "打开", "翻开", "开"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_open(ctx, user_id, args)
