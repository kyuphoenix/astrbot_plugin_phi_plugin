from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"help", "帮助", "菜单", "命令", "指令"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if ctx.config.render_mode == "image":
        return CommandResult.image(await render_jinja_template(ctx, "help/help", jinja_adapter.help_data(ctx.paths), "help"))
    return CommandResult.text(render.render_help())
