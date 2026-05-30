from __future__ import annotations

from typing import Any

from .common import CommandContext
from ..query import merge_histories
from ..save import SaveNotAvailable


async def load_merged_history(ctx: CommandContext, user_id: str, fields: list[str]) -> dict[str, Any]:
    history = ctx.store.load_history(user_id)
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if token or api_id:
        try:
            remote = await ctx.client.fetch_history(user_id, token=token, api_id=api_id, fields=fields)
            history = merge_histories(remote, history)
            ctx.store.save_history(user_id, history)
        except SaveNotAvailable:
            pass
    return history
