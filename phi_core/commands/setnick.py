from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data import apply_aliases
from ..data.loader import normalize_key
from ..render import text as render

ALIASES = {"setnick", "setnic", "设置别名"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not ctx.is_admin:
        return CommandResult.text("只有管理员可以设置别名。")

    source, alias = _parse_alias_args(args)
    if not source or not alias:
        return CommandResult.text("输入有误。\n格式：phi setnick 原名（或已有别名） ---> 新别名")

    song = ctx.searcher.best(source)
    if not song:
        return CommandResult.text(render.render_search(source, []))

    alias_key = normalize_key(alias)
    existing_id = ctx.catalog.alias_to_id.get(alias_key)
    if existing_id == song.id:
        return CommandResult.text(f"{song.title} 已经有「{alias}」这个别名了。")
    if existing_id and existing_id != song.id:
        existing_song = ctx.catalog.get(existing_id)
        existing_name = existing_song.title if existing_song else existing_id
        return CommandResult.text(f"「{alias}」已经指向「{existing_name}」，为避免误匹配未写入。")

    added = ctx.store.add_custom_alias(song.id, alias)
    apply_aliases(ctx.catalog, {song.id: [alias]})
    if not added:
        return CommandResult.text(f"{song.title} 已经有「{alias}」这个别名了。")
    return CommandResult.text(f"设置完成：{song.title} -> {alias}")


def _parse_alias_args(args: str) -> tuple[str, str]:
    text = args.strip()
    if "--->" in text:
        left, right = text.split("--->", 1)
        return left.strip(), right.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[0], lines[1]
    return "", ""
