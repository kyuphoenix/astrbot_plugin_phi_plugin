from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"live"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    try:
        info = await ctx.client.live_info()
    except SaveNotAvailable:
        return CommandResult.text(render.render_live_info(""))
    return CommandResult.text(render.render_live_info(info))
