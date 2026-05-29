from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..query import compute_average_rks, top_records
from ..render import text as render

ALIASES = {"p30"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    limit = _limit_from_args(args, 30)
    records = top_records(snapshot, ctx.catalog, limit=limit, mode="p")
    return CommandResult.text(render.render_records(f"All Perfect Top {limit}", records, official_rks=snapshot.ranking_score, average_rks=compute_average_rks(records)))


def _limit_from_args(args: str, default: int) -> int:
    match = re.search(r"\d+", args)
    if not match:
        return default
    return max(1, min(50, int(match.group(0))))
