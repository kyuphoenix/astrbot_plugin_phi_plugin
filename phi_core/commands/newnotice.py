from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..data import load_notice
from ..render import original
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"newnotice"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    notice = await _load_online_notice(ctx)
    if ctx.config.render_mode == "image":
        path = await render_original_html(ctx, original.notice_html(ctx.paths, notice), "newnotice")
        return CommandResult.image(path)
    return CommandResult.text(render.render_notice(notice))


async def _load_online_notice(ctx: CommandContext) -> dict:
    try:
        notices = await ctx.client.fetch_taptap_notices(limit=1)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        notices = []
    if notices:
        return {"info": notices}
    return load_notice(ctx.paths.info)
