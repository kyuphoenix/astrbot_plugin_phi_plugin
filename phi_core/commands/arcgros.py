from __future__ import annotations

from ._b30_common import _attach_acc_averages, _limit_from_args
from ._rendering import render_jinja_template
from .common import CommandContext, CommandResult
from ..query import compute_b30
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"arcgros", "arcgrosb19"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    requested_limit = _limit_from_args(args)
    limit = max(33, requested_limit or ctx.config.max_b30)
    result = compute_b30(snapshot, ctx.catalog, limit=limit)
    await _attach_acc_averages(ctx, result)
    if ctx.config.render_mode == "image":
        path = await render_jinja_template(
            ctx,
            "arcgrosB19/arcgrosB19",
            jinja_adapter.arcgros_b19_data(ctx.paths, result, snapshot),
            "arcgros",
        )
        return CommandResult.image(path)
    text = render.render_b30(result, limit=limit)
    if text.startswith("官方 RKS"):
        text = "Arcgros style score query (text equivalent)\n" + text
    return CommandResult.text(text)
