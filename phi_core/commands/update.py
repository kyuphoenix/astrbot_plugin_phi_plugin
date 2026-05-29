from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import summarize_user
from ..render import text as render
from ..save import SaveNotAvailable, normalize_save, snapshot_to_json

ALIASES = {"update", "更新存档"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())
    try:
        try:
            raw = await ctx.client.fetch_cloud_save(token, user_id=user_id, api_id=api_id)
        except SaveNotAvailable:
            if not token or not api_id:
                raise
            raw = await ctx.client.fetch_cloud_save(None, user_id=user_id, api_id=api_id)
        snapshot = normalize_save(user_id, token or "", raw)
        raw_api_id = raw.get("apiId") or raw.get("api_id") or raw.get("internal_id")
        if raw_api_id and ctx.store.validate_api_id(str(raw_api_id)):
            ctx.store.set_api_id(user_id, str(raw_api_id))
        ctx.store.save_snapshot(user_id, snapshot_to_json(snapshot))
        return CommandResult.text(render.render_update_ok(summarize_user(snapshot, ctx.catalog)))
    except SaveNotAvailable as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))
    except Exception as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))
