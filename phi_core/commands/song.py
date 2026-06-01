from __future__ import annotations

from typing import Any

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..render import jinja_adapter
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"song", "\u66f2"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    query, with_comments = _parse_args(args)
    if not query:
        return CommandResult.text(render.render_need_query("song"))
    song = ctx.searcher.best(query)
    if not song:
        return CommandResult.text(render.render_search(query, []))
    comments: dict[str, Any] | None = None
    if with_comments:
        try:
            raw_comments = await ctx.client.fetch_comments_by_song(song.id)
        except SaveNotAvailable:
            raw_comments = []
        comments = {
            "command": f"当前共有{len(raw_comments)}条评论，发送 phi cmt <曲名> <定级?>(换行)<内容> 进行评论",
            "list": raw_comments[:10],
            "total": len(raw_comments),
        }
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_jinja_template(
            ctx,
            "atlas/atlas",
            jinja_adapter.atlas_data(ctx.paths, song, comments=comments),
            "song",
            width=2048,
        )
        return CommandResult.image(path)
    if with_comments:
        return CommandResult.text(render.render_comments(song, (comments or {}).get("list", [])))
    return CommandResult.text(render.render_song(song))


def _parse_args(args: str) -> tuple[str, bool]:
    text = (args or "").strip()
    with_comments = "-comment" in text.casefold()
    if with_comments:
        text = text.replace("-comment", " ").replace("-COMMENT", " ")
    return " ".join(text.split()), with_comments
