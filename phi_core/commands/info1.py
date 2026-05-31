from __future__ import annotations

from .common import CommandContext, CommandResult
from .info import render_info

ALIASES = {"info1"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await render_info(ctx, user_id, args, variant=1)
