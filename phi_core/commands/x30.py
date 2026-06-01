from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..models import Best30Result
from ..query import compute_average_rks, top_records
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"x30"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    limit = _limit_from_args(args, 30)
    records = top_records(snapshot, ctx.catalog, limit=limit, mode="x")
    average_rks = compute_average_rks(records)
    if ctx.config.render_mode == "image":
        image_limit = max(33, limit)
        image_records = top_records(snapshot, ctx.catalog, limit=image_limit, mode="x")
        image_average_rks = compute_average_rks(image_records)
        result = Best30Result(
            official_rks=snapshot.ranking_score,
            computed_rks=image_average_rks,
            records=image_records,
            total_records=len(image_records),
        )
        path = await render_jinja_template(
            ctx,
            "b19/b19",
            jinja_adapter.b30_data(
                ctx.paths,
                result,
                snapshot,
                sp_info=["1 Good Mode", f"Computed RKS: {image_average_rks:.4f}"],
                display_rks=image_average_rks,
            ),
            "x30",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_records(f"1 Good Top {limit}", records, official_rks=snapshot.ranking_score, average_rks=average_rks))


def _limit_from_args(args: str, default: int) -> int:
    match = re.search(r"\d+", args)
    if not match:
        return default
    return max(1, min(50, int(match.group(0))))
