from __future__ import annotations

from collections.abc import Callable

from .common import CommandContext, CommandResult
from ..render import text as render


def make_unsupported_handler(command_name: str) -> Callable[[CommandContext, str, str], CommandResult]:
    def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
        return CommandResult.text(render.render_unsupported(f"phi {command_name}"))

    return handle
