from __future__ import annotations

from typing import Any

import yaml

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..query import compute_chapter_summary, iter_score_records
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"chap"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    query = args.strip()
    if not query or query.casefold() == "help":
        help_img = ctx.paths.resources / "html" / "otherimg" / "chapHelp.png"
        if ctx.config.render_mode == "image" and help_img.exists():
            return CommandResult.image(help_img)
        return CommandResult.text(_chapter_help(ctx))

    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    chapter = _resolve_chapter_alias(ctx, query)
    summary = compute_chapter_summary(iter_score_records(snapshot, ctx.catalog), ctx.catalog, chapter or query)
    if summary is None:
        return CommandResult.text(f"\u672a\u627e\u5230\u300c{query}\u300d\u7ae0\u8282\u3002\u53ef\u4ee5\u4f7f\u7528 phi chap help \u67e5\u770b\u652f\u6301\u7684\u540d\u79f0\u3002")
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_jinja_template(
            ctx,
            "chap/chap",
            jinja_adapter.chap_data(ctx.paths, summary, snapshot=snapshot, catalog=ctx.catalog),
            "chap",
            width=2048,
            height=1080,
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_chapter_summary(summary))


def _chapter_help(ctx: CommandContext) -> str:
    aliases = _load_chapter_aliases(ctx)
    lines = ["\u7ae0\u8282\u6210\u7ee9\u67e5\u8be2", "\u683c\u5f0f\uff1aphi chap <\u7ae0\u8282\u540d|\u522b\u540d|all>", "", "\u652f\u6301\u7ae0\u8282\uff1a"]
    for name, values in aliases.items():
        preview = " / ".join(str(item) for item in values[:4])
        lines.append(f"- {name}" + (f" ({preview})" if preview else ""))
    lines.append("- all / \u5168\u90e8")
    return "\n".join(lines)


def _resolve_chapter_alias(ctx: CommandContext, query: str) -> str | None:
    key = _normalize(query)
    if key in {"all", "allsong", "\u5168\u90e8"}:
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
