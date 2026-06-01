from __future__ import annotations

from pathlib import Path

from ._history_common import load_merged_history
from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..data.illustrations import background_illustration_url, find_background_illustration_file, use_remote_illustrations
from ..query import summarize_user
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"info"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    return await render_info(ctx, user_id, args, variant=1)


async def render_info(ctx: CommandContext, user_id: str, args: str, *, variant: int = 1) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    history = await load_merged_history(ctx, user_id, ["data", "rks", "scoreHistory", "challengeModeRank"])
    background = _requested_background(ctx, args)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await render_jinja_template(
            ctx,
            "userinfo/userinfo" if variant == 1 else "userinfo/userinfo-old",
            jinja_adapter.userinfo_data(
                ctx.paths,
                summarize_user(snapshot, ctx.catalog),
                snapshot=snapshot,
                history=history,
                catalog=ctx.catalog,
                background=background,
            ),
            "info" if variant == 1 else "info-old",
            width=1920 if variant == 1 else 1800,
            height=1500 if variant == 1 else None,
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_user_info(summarize_user(snapshot, ctx.catalog)))


def _requested_background(ctx: CommandContext, args: str) -> str | Path | None:
    query = (args or "").strip()
    if not query:
        return None
    song = ctx.searcher.best(query)
    if song is None:
        return None
    if use_remote_illustrations(ctx.paths):
        return background_illustration_url(song.id, paths=ctx.paths)
    path = find_background_illustration_file(ctx.paths, song.id) or find_background_illustration_file(ctx.paths, song.id_with_suffix)
    if path is not None:
        return path
    return None
