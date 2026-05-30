from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data import remove_alias
from ..render import text as render

ALIASES = {"delnick", "delnic", "删除别名"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not ctx.is_admin:
        return CommandResult.text("只有管理员可以删除别名。")
    source, alias = _parse_alias_args(args)
    if not source or not alias:
        return CommandResult.text("输入有误。\n格式：phi delnick 原名（或已有别名） ---> 要删除的别名")

    song = ctx.searcher.best(source)
    if not song:
        return CommandResult.text(render.render_search(source, []))

    removed = ctx.store.remove_custom_alias(song.id, alias)
    if not removed:
        return CommandResult.text(f"{song.title} 没有本地自定义别名「{alias}」，或该别名来自原版资源不能在这里删除。")
    remove_alias(ctx.catalog, song.id, alias)
    return CommandResult.text(f"删除完成：{song.title} -/-> {alias}")


def _parse_alias_args(args: str) -> tuple[str, str]:
    text = args.strip()
    if "--->" in text:
        left, right = text.split("--->", 1)
        return left.strip(), right.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[0], lines[1]
    return "", ""
