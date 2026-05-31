from __future__ import annotations

from typing import Any

from .common import CommandContext, CommandResult
from ..save import SaveNotAvailable

ALIASES = {"tokenlist", "tkls", "lstk"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    if not token:
        return CommandResult.text("本地没有你的 sessionToken 记录，请先使用 phi bind 绑定。")

    try:
        data = await ctx.client.token_list(user_id, token)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"获取 Token 列表失败：{exc}")

    platforms = data.get("platform_data") if isinstance(data, dict) else None
    if not isinstance(platforms, list):
        platforms = []
    if not platforms:
        return CommandResult.text("当前 API 账户没有已绑定的平台。")

    lines = [f"已绑定 {len(platforms)} 个平台"]
    for index, item in enumerate(platforms, 1):
        if not isinstance(item, dict):
            continue
        current = _is_current_platform(item, user_id)
        lines.append(f"{index}.{'（当前）' if current else ''}")
        lines.append(f"平台: {_value(item, 'platform_name', 'platform')}")
        lines.append(f"平台ID: {_value(item, 'platform_id', 'platformId')}")
        lines.append(f"创建时间: {_value(item, 'create_at', 'createAt')}")
        lines.append(f"更新时间: {_value(item, 'update_at', 'updateAt')}")
        lines.append(f"权限: {_value(item, 'authentication', 'auth')}")
    return CommandResult.text("\n".join(lines))


def _value(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return str(value)
    return "-"


def _is_current_platform(item: dict[str, Any], user_id: str) -> bool:
    platform = str(item.get("platform_name") or item.get("platform") or "")
    platform_id = str(item.get("platform_id") or item.get("platformId") or "")
    return platform.casefold() == "astrbot" and platform_id == str(user_id)
