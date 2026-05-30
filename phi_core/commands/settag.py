from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..models import LEVELS, Song
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"settag"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())

    song_query, rank, requested_tags = await _parse_args(ctx, args)
    if not song_query:
        return CommandResult.text("格式：phi settag <曲名> [EZ|HD|IN|AT] <标签1> <标签2> ...")
    song = ctx.searcher.best(song_query)
    if not song:
        return CommandResult.text(render.render_search(song_query, []))
    if rank not in song.charts:
        return CommandResult.text(_missing_rank(song, rank))
    if not requested_tags:
        return CommandResult.text(await _tag_help(ctx))

    try:
        await ctx.client.set_chart_tags(user_id, token=token, api_id=api_id, song_id=song.id, rank=rank, tags=requested_tags)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"投票失败：{exc}")
    return CommandResult.text(f"谱面标签已提交：{song.title} {rank} -> {'、'.join(requested_tags)}")


async def _parse_args(ctx: CommandContext, args: str) -> tuple[str, str, list[str]]:
    text = args.strip()
    if not text:
        return "", "IN", []
    tag_names = await _tag_names(ctx)
    selected_tags = _selected_tags(text, tag_names)
    rank = "IN"
    rank_match = re.search(r"\b(EZ|HD|IN|AT)\b", text, flags=re.IGNORECASE)
    if rank_match:
        rank = rank_match.group(1).upper()
        text = (text[:rank_match.start()] + text[rank_match.end():]).strip()
    for tag in selected_tags:
        text = re.sub(rf"(^|\s)({re.escape(tag)})(?=\s|$)", " ", text).strip()
    for index, tag in enumerate(tag_names, 1):
        if tag in selected_tags:
            text = re.sub(rf"(^|\s)({index})(?=\s|$)", " ", text).strip()
    return " ".join(text.split()), rank, selected_tags


async def _tag_names(ctx: CommandContext) -> list[str]:
    try:
        return await ctx.client.fetch_chart_tag_names()
    except SaveNotAvailable:
        return []


def _selected_tags(text: str, tag_names: list[str]) -> list[str]:
    selected: list[str] = []
    for index, tag in enumerate(tag_names, 1):
        if re.search(rf"(^|\s)({re.escape(tag)}|{index})(?=\s|$)", text):
            selected.append(tag)
    if selected:
        return selected
    parts = [part.strip() for part in text.split() if part.strip()]
    return [part for part in parts if not re.fullmatch(r"EZ|HD|IN|AT", part, flags=re.IGNORECASE)][1:]


async def _tag_help(ctx: CommandContext) -> str:
    tags = await _tag_names(ctx)
    if not tags:
        return "请在命令后添加要投票的标签。格式：phi settag <曲名> [难度] <标签1> <标签2> ..."
    lines = ["请在命令后添加要投票的标签。可选标签有："]
    lines.extend(f"- {index}. {tag}" for index, tag in enumerate(tags, 1))
    lines.append("可以使用序号，多个标签之间用空格分隔。")
    return "\n".join(lines)


def _missing_rank(song: Song, rank: str) -> str:
    ranks = " / ".join(chart.rank for chart in song.display_charts())
    return f"「{song.title}」没有 {rank} 谱面。可用难度：{ranks or '暂无'}"
