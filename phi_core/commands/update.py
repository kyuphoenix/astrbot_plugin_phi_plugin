from __future__ import annotations

from .common import CommandContext, CommandResult
from ._sync import sync_save_with_progress
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"update", "更新存档"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())
    try:
        result = await sync_save_with_progress(ctx, user_id)
        return CommandResult.text(render.render_update_progress(result.progress))
    except SaveNotAvailable as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))
    except Exception as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))
