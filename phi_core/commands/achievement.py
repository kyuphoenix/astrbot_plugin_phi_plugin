from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..query import compute_achievement_rows, iter_score_records
from ..render import text as render

ALIASES = {"achievement", "ahv"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    match = re.search(r"\d+", args)
    if not match:
        return CommandResult.text("请输入定数整数。\n格式：phi achievement <定数整数>")
    difficulty_floor = int(match.group(0))
    if difficulty_floor < 1:
        return CommandResult.text("定数不能小于 1。")
    rows = compute_achievement_rows(iter_score_records(snapshot, ctx.catalog), ctx.catalog, difficulty_floor)
    return CommandResult.text(render.render_achievement(rows, difficulty_floor))
