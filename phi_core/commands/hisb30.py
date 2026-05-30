from __future__ import annotations

from ._history_common import load_merged_history
from .common import CommandContext, CommandResult
from ..query import compute_history_b30_changes
from ..render import text as render

ALIASES = {"hisb30"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    history = await load_merged_history(ctx, user_id, ["scoreHistory"])
    if not history:
        return CommandResult.text("还没有可用的历史记录。请先使用 phi update。")
    changes = compute_history_b30_changes(history, ctx.catalog)
    return CommandResult.text(render.render_history_b30(changes))
