from __future__ import annotations

from .common import CommandContext, CommandResult
from ._b30_common import render_best30

ALIASES = {"rks"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return render_best30(ctx, user_id, args)
