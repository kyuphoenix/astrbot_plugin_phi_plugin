from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import panel
from ..render import text as render

ALIASES = {"help", "帮助", "菜单", "命令", "指令"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if ctx.config.render_mode == "image":
        return CommandResult.image(await panel.render_help_panel(ctx.config, ctx.paths, html_render=ctx.html_render))
    return CommandResult.text(render.render_help())
