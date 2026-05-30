from __future__ import annotations

from ._history_common import load_merged_history
from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import analyze_history
from ..render import original
from ..render import text as render

ALIASES = {"2025history", "\u5e74\u5ea6\u603b\u7ed3"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    history = await load_merged_history(ctx, user_id, ["challengeModeRank", "data", "rks", "scoreHistory"])
    if not history:
        return CommandResult.text("\u8fd8\u6ca1\u6709\u53ef\u7528\u7684\u5386\u53f2\u8bb0\u5f55\u3002\u8bf7\u5148\u4f7f\u7528 phi update\u3002")
    summary = analyze_history(history, ctx.catalog)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.history_summary_html(ctx.paths, summary), "history2025")
        return CommandResult.image(path)
    return CommandResult.text(render.render_history_summary(summary))
