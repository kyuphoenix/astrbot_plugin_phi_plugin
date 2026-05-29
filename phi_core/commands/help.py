from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import image
from ..render import text as render

ALIASES = {"help", "帮助", "菜单", "命令", "指令"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if ctx.config.render_mode == "image":
        return CommandResult.image(image.render_help_panel(ctx.paths))
    return CommandResult.text(render.render_help())
