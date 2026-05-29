from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"help", "帮助", "菜单", "命令", "指令"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return CommandResult.text(render.render_help())
