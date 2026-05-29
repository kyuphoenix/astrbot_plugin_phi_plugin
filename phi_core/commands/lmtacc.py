from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import compute_average_rks, top_records
from ..render import text as render

ALIASES = {"lmtacc"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    try:
        acc = float(args.strip().rstrip("%"))
    except ValueError:
        return CommandResult.text("请指定一个 0-100 的数字。\n格式：phi lmtacc <0-100>")
    if acc < 0 or acc > 100:
        return CommandResult.text("ACC 下限必须在 0-100 之间。")
    records = top_records(snapshot, ctx.catalog, limit=ctx.config.max_b30, min_acc=acc)
    return CommandResult.text(render.render_records(f"ACC >= {acc:g}% Top {ctx.config.max_b30}", records, official_rks=snapshot.ranking_score, average_rks=compute_average_rks(records)))
