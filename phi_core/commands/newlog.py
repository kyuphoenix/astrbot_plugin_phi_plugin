from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..data import latest_version_log, load_version_log, resolve_version_code
from ..render import original
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"newlog"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    version = resolve_version_code(ctx.paths.info, args.strip()) if args.strip() else None
    log = load_version_log(ctx.paths.info, version) if version is not None else latest_version_log(ctx.paths.info)
    update_logs = await _load_online_update_logs(ctx) if version is None else []
    if ctx.config.render_mode == "image":
        image = CommandResult.image(await render_original_html(
            ctx,
            original.newlog_html(ctx.paths, log, catalog=ctx.catalog, update_logs=update_logs),
            "newlog",
        ))
        if ctx.sender is not None:
            await ctx.sender(image)
            return CommandResult.text(render.render_newlog(log, update_logs=update_logs, include_changes=False))
        return image
    return CommandResult.text(render.render_newlog(log, update_logs=update_logs))


async def _load_online_update_logs(ctx: CommandContext) -> list[dict]:
    try:
        return await ctx.client.fetch_taptap_update_logs(limit=1)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        return []
