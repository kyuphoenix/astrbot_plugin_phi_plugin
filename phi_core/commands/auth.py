from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..render import text as render
from ..save import SaveNotAvailable, StoreError

ALIASES = {"auth", "login", "登录"}
_UNSAFE_API_TOKEN_RE = re.compile(r"[\s\x00-\x1F\x7F'\"\\]")


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    api_token = args.strip().split()[0] if args.strip() else ""
    if not api_token:
        return CommandResult.text(render.render_auth_need_token())
    if _UNSAFE_API_TOKEN_RE.search(api_token):
        return CommandResult.text("API Token 包含空白或非法字符，请检查后重试。")

    try:
        old_token = ctx.store.get_token(user_id)
        result = await ctx.client.get_pgr_token(user_id, api_token)
        ctx.store.bind(user_id, result.token)
        if old_token != result.token:
            ctx.store.clear_snapshot(user_id)
        api_id = result.api_id if result.api_id and ctx.store.validate_api_id(result.api_id) else None
        if api_id:
            ctx.store.set_api_id(user_id, api_id)
        else:
            ctx.store.clear_api_id(user_id)
        return CommandResult.text(render.render_auth_ok(api_id=api_id))
    except (SaveNotAvailable, StoreError) as exc:
        return CommandResult.text(f"登录失败：{exc}")
