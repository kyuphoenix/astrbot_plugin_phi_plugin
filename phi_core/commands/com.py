from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import rks_from_acc
from ..render import text as render

ALIASES = {"com", "计算"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    parts = args.split()
    if len(parts) < 2:
        return CommandResult.text("格式错误。\n格式：phi com <定数> <acc>")
    try:
        difficulty = float(parts[0])
        acc = float(parts[1].rstrip("%"))
    except ValueError:
        return CommandResult.text("格式错误。\n格式：phi com <定数> <acc>")
    if difficulty <= 0 or difficulty > 18 or acc <= 0 or acc > 100:
        return CommandResult.text("定数应在 0-18 之间，ACC 应在 0-100 之间。")
    return CommandResult.text(render.render_com(difficulty, acc, rks_from_acc(acc, difficulty)))
