from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..save import SaveNotAvailable

ALIASES = {"rankfind", "查询排名"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    rks = _rks_from_args(args)
    if rks is None:
        return CommandResult.text("请输入要查询的 rks，例如：phi rankfind 15.2")
    try:
        data = await ctx.client.fetch_ranklist_rks_rank(rks)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"查询排名失败：{exc}")
    rank = data.get("rksRank") or data.get("rank") or 0
    total = data.get("totNum") or data.get("totDataNum") or 0
    return CommandResult.text(f"当前服务器记录中一共有 {rank}/{total} 位玩家的 rks 大于 {rks:g}！")


def _rks_from_args(args: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", args or "")
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
