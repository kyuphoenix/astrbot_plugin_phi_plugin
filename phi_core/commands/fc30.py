from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import compute_average_rks, top_records
from ..render import original
from ..render import text as render

ALIASES = {"fc30"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    limit = _limit_from_args(args, 30)
    records = top_records(snapshot, ctx.catalog, limit=limit, mode="fc")
    average_rks = compute_average_rks(records)
    if ctx.config.render_mode == "image":
        path = await render_original_html(
            ctx,
            original.record_list_html(
                ctx.paths,
                records,
                snapshot,
                title=f"Full Combo Top {limit}",
                sp_info=["Full Combo Mode", f"Computed RKS: {average_rks:.4f}"],
                limit_label="F",
            ),
            "fc30",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_records(f"Full Combo Top {limit}", records, official_rks=snapshot.ranking_score, average_rks=average_rks))


def _limit_from_args(args: str, default: int) -> int:
    match = re.search(r"\d+", args)
    if not match:
        return default
    return max(1, min(50, int(match.group(0))))
