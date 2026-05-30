from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..models import LEVELS
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"addtag", "subtag", "retag"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    song_query, rank, tags = _parse_args(args)
    if not song_query:
        return CommandResult.text("格式：phi addtag <曲名> <EZ|HD|IN|AT> <标签1> <标签2> ...\n查看标签：phi addtag <曲名> <难度>")
    song = ctx.searcher.best(song_query)
    if not song:
        return CommandResult.text(render.render_search(song_query, []))
    if not rank:
        rank = "IN"
    if rank not in LEVELS:
        return CommandResult.text(f"{rank} 不是可用难度。")

    if not tags:
        try:
            tag_data = await ctx.client.fetch_chart_tags(song.id, rank)
        except SaveNotAvailable as exc:
            return CommandResult.text(f"获取谱面标签失败：{exc}")
        return CommandResult.text(render.render_chart_tags(song, rank, tag_data))

    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())
    try:
        await ctx.client.set_chart_tags(user_id, token=token, api_id=api_id, song_id=song.id, rank=rank, tags=tags)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"设置谱面标签失败：{exc}")
    return CommandResult.text(f"谱面标签已提交：{song.title} {rank} -> {'、'.join(tags)}")


def _parse_args(args: str) -> tuple[str, str, list[str]]:
    parts = args.strip().split()
    if not parts:
        return "", "", []
    rank = ""
    rank_index = -1
    for index, part in enumerate(parts):
        if re.fullmatch(r"EZ|HD|IN|AT", part, flags=re.IGNORECASE):
            rank = part.upper()
            rank_index = index
            break
    if rank_index < 0:
        return " ".join(parts), "", []
    song_query = " ".join(parts[:rank_index]).strip()
    tags = [part.strip() for part in parts[rank_index + 1:] if part.strip()]
    return song_query, rank, tags
