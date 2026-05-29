from __future__ import annotations

from .common import CommandContext, CommandResult
from ..query import find_song_scores
from ..render import text as render

ALIASES = {"score", "单曲成绩"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("score"))
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    song = ctx.searcher.best(args)
    if not song:
        return CommandResult.text(render.render_search(args, []))
    return CommandResult.text(render.render_score(song, find_song_scores(snapshot, ctx.catalog, song)))
