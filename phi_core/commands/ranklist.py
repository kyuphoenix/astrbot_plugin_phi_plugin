from __future__ import annotations

import re

from ._rendering import render_jinja_template
from .common import CommandContext, CommandResult
from ..render import jinja_adapter
from ..save import SaveNotAvailable

ALIASES = {"ranklist", "排行榜"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    rank = _rank_from_args(args)
    try:
        data = await ctx.client.fetch_ranklist_rank(rank) if rank is not None else await ctx.client.fetch_ranklist_user(user_id)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"获取排行榜失败：{exc}")

    if ctx.config.render_mode == "image":
        legacy = ctx.config.ranklist_image_version == "old"
        template = "rankingList-old/rankingList" if legacy else "rankingList/rankingList"
        image_data = (
            jinja_adapter.ranking_list_old_data(ctx.paths, data, ctx.catalog)
            if legacy
            else jinja_adapter.ranking_list_data(ctx.paths, data, ctx.catalog)
        )
        path = await render_jinja_template(
            ctx,
            template,
            image_data,
            "ranklist",
            width=800 if legacy else 2048,
            height=None if legacy else 1080,
        )
        return CommandResult.image(path)
    return CommandResult.text(_ranklist_text(data))


def _rank_from_args(args: str) -> int | None:
    match = re.search(r"\d+", args or "")
    if not match:
        return None
    return max(1, int(match.group(0)))


def _ranklist_text(data: dict) -> str:
    total = data.get("totDataNum") or data.get("totNum") or 0
    users = data.get("users") if isinstance(data.get("users"), list) else []
    lines = ["RankingScore 排行榜", f"总数据量：{total}"]
    for item in users[:5]:
        if not isinstance(item, dict):
            continue
        save_info = item.get("saveInfo") if isinstance(item.get("saveInfo"), dict) else {}
        summary = save_info.get("summary") if isinstance(save_info.get("summary"), dict) else {}
        gameuser = item.get("gameuser") if isinstance(item.get("gameuser"), dict) else {}
        index = item.get("index") or "?"
        player = save_info.get("PlayerId") or gameuser.get("PlayerId") or gameuser.get("name") or "NO INFO"
        try:
            rks = float(summary.get("rankingScore") or gameuser.get("rankingScore") or 0)
        except (TypeError, ValueError):
            rks = 0.0
        mark = " <- YOU" if item.get("me") else ""
        lines.append(f"#{index} {player} RKS {rks:.4f}{mark}")
    return "\n".join(lines)
