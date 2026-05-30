from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import compute_average_rks, top_records
from ..render import original
from ..render import text as render

ALIASES = {"best"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    try:
        limit = int(args.strip() or "19")
    except ValueError:
        return CommandResult.text("格式错误。\n格式：phi best [数量]")
    limit = max(1, min(50, limit))
    records = top_records(snapshot, ctx.catalog, limit=limit)
    average_rks = compute_average_rks(records)
    if ctx.config.render_mode == "image":
        path = await render_original_html(
            ctx,
            original.record_list_html(
                ctx.paths,
                records,
                snapshot,
                title=f"Best {limit}",
                sp_info=[f"Best {limit} Mode", f"Computed RKS: {average_rks:.4f}"],
            ),
            "best",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_records(f"Best {limit}", records, official_rks=snapshot.ranking_score, average_rks=average_rks))
