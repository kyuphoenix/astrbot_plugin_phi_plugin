from __future__ import annotations

from ._history_common import load_merged_history
from .common import CommandContext, CommandResult
from ..query import analyze_history
from ..render import text as render

ALIASES = {"2025history", "年度总结"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    history = await load_merged_history(ctx, user_id, ["challengeModeRank", "data", "rks", "scoreHistory"])
    if not history:
        return CommandResult.text("还没有可用的历史记录。请先使用 phi update。")
    return CommandResult.text(render.render_history_summary(analyze_history(history, ctx.catalog)))
