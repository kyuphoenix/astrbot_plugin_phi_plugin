from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..render import original
from ..render import text as render

ALIASES = {"help", "帮助", "菜单", "命令", "指令"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if ctx.config.render_mode == "image":
        return CommandResult.image(await render_original_html(ctx, original.help_html(ctx.paths), "help"))
    return CommandResult.text(render.render_help())
