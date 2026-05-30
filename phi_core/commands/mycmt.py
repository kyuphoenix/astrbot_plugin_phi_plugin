from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"mycmt"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())
    try:
        comments = await ctx.client.fetch_comments_by_user(user_id, token=token, api_id=api_id)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"获取我的评论失败：{exc}")
    return CommandResult.text(render.render_my_comments(comments))
