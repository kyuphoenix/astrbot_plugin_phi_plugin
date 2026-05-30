from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import compute_average_rks, top_records
from ..render import original
from ..render import text as render

ALIASES = {"lmtacc"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    try:
        acc = float(args.strip().rstrip("%"))
    except ValueError:
        return CommandResult.text("\u8bf7\u6307\u5b9a\u4e00\u4e2a 0-100 \u7684\u6570\u5b57\u3002\n\u683c\u5f0f\uff1aphi lmtacc <0-100>")
    if acc < 0 or acc > 100:
        return CommandResult.text("ACC \u4e0b\u9650\u5fc5\u987b\u5728 0-100 \u4e4b\u95f4\u3002")
    records = top_records(snapshot, ctx.catalog, limit=ctx.config.max_b30, min_acc=acc)
    average_rks = compute_average_rks(records)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(
            ctx,
            original.record_list_html(
                ctx.paths,
                records,
                snapshot,
                title=f"ACC >= {acc:g}% Top {ctx.config.max_b30}",
                sp_info=["Limit ACC Mode", f"Computed RKS: {average_rks:.4f}"],
                limit_label="L",
            ),
            "lmtacc",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_records(f"ACC >= {acc:g}% Top {ctx.config.max_b30}", records, official_rks=snapshot.ranking_score, average_rks=average_rks))
