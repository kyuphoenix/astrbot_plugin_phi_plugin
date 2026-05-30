from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..query import find_song_scores
from ..render import original
from ..render import text as render

ALIASES = {"score", "\u5355\u66f2\u6210\u7ee9"}


def _clean_query(args: str) -> str:
    text = args
    for marker in ("-dif", "-or", "-unrank"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    query = _clean_query(args)
    if not query:
        return CommandResult.text(render.render_need_query("score"))
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    song = ctx.searcher.best(query)
    if not song:
        return CommandResult.text(render.render_search(query, []))
    records = find_song_scores(snapshot, ctx.catalog, song)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_original_html(ctx, original.score_html(ctx.paths, song, records, snapshot), "score")
        return CommandResult.image(path)
    return CommandResult.text(render.render_score(song, records))
