from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import compute_achievement_rows, iter_score_records
from ..render import original
from ..render import text as render

ALIASES = {"achievement", "ahv"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    match = re.search(r"\d+", args)
    if not match:
        return CommandResult.text("\u8bf7\u8f93\u5165\u5b9a\u6570\u6574\u6570\u3002\n\u683c\u5f0f\uff1aphi achievement <\u5b9a\u6570\u6574\u6570>")
    difficulty_floor = int(match.group(0))
    if difficulty_floor < 1:
        return CommandResult.text("\u5b9a\u6570\u4e0d\u80fd\u5c0f\u4e8e 1\u3002")
    rows = compute_achievement_rows(iter_score_records(snapshot, ctx.catalog), ctx.catalog, difficulty_floor)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.achievement_html(ctx.paths, rows, title=f"Player Achievements {difficulty_floor}.0-{difficulty_floor}.9"), "achievement")
        return CommandResult.image(path)
    return CommandResult.text(render.render_achievement(rows, difficulty_floor))
