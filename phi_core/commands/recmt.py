from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..save import SaveNotAvailable

ALIASES = {"recmt"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    if not token:
        return CommandResult.text("请先绑定 sessionToken 后再删除评论。")
    match = re.search(r"\d+", args)
    if not match:
        return CommandResult.text("请输入评论 ID。\n格式：phi recmt <评论ID>")
    try:
        await ctx.client.delete_comment(user_id, token, match.group(0))
    except SaveNotAvailable as exc:
        return CommandResult.text(f"删除在线评论失败：{exc}")
    return CommandResult.text("删除在线评论成功。")
