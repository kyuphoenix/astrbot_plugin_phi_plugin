from __future__ import annotations

from .common import CommandContext, CommandResult
from ._games import handle_letter

ALIASES = {"ltr", "letter", "开字母"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await handle_letter(ctx, user_id, args)
