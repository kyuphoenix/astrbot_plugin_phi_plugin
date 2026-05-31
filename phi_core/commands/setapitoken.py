from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..save import SaveNotAvailable

ALIASES = {"setapitoken"}
_UNSAFE_API_TOKEN_RE = re.compile(r"[\s\x00-\x1F\x7F'\"\\]")


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    if not token:
        return CommandResult.text("本地没有你的 sessionToken 记录，请先使用 phi bind 绑定。")

    api_token = args.strip().split()[0] if args.strip() else ""
    if not api_token:
        return CommandResult.text("请输入 API Token。\n格式：phi setApiToken <新Token>")
    if _UNSAFE_API_TOKEN_RE.search(api_token):
        return CommandResult.text("API Token 包含空白或非法字符，请检查后重试。\n格式：phi setApiToken <新Token>")

    try:
        await ctx.client.set_api_token(user_id, token, api_token)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"设置 API Token 失败：{exc}")
    return CommandResult.text("API Token 已设置为：\n" + api_token)
