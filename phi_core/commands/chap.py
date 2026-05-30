from __future__ import annotations

from typing import Any

import yaml

from .common import CommandContext, CommandResult
from ..query import compute_chapter_summary, iter_score_records
from ..render import text as render

ALIASES = {"chap"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    query = args.strip()
    if not query or query.casefold() == "help":
        return CommandResult.text(_chapter_help(ctx))

    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    chapter = _resolve_chapter_alias(ctx, query)
    summary = compute_chapter_summary(iter_score_records(snapshot, ctx.catalog), ctx.catalog, chapter or query)
    if summary is None:
        return CommandResult.text(f"未找到「{query}」章节。可以使用 phi chap help 查看支持的名称。")
    return CommandResult.text(render.render_chapter_summary(summary))


def _chapter_help(ctx: CommandContext) -> str:
    aliases = _load_chapter_aliases(ctx)
    lines = ["章节成绩查询", "格式：phi chap <章节名|别名|all>", "", "支持章节："]
    for name, values in aliases.items():
        preview = " / ".join(str(item) for item in values[:4])
        lines.append(f"- {name}" + (f" ({preview})" if preview else ""))
    lines.append("- all / 全部")
    return "\n".join(lines)


def _resolve_chapter_alias(ctx: CommandContext, query: str) -> str | None:
    key = _normalize(query)
    if key in {"all", "allsong", "全部"}:
        return "ALL"
    for name, values in _load_chapter_aliases(ctx).items():
        if _normalize(name) == key:
            return name
        for value in values:
            if _normalize(str(value)) == key:
                return name
    return None


def _load_chapter_aliases(ctx: CommandContext) -> dict[str, list[Any]]:
    path = ctx.paths.info / "chaplist.yaml"
    if not path.exists():
        chapters = sorted({song.chapter for song in ctx.catalog.all_songs() if song.chapter})
        return {chapter: [] for chapter in chapters}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value if isinstance(value, list) else [] for key, value in data.items()}


def _normalize(value: str) -> str:
    return "".join(str(value).casefold().split())
