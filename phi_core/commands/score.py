from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .common import CommandContext, CommandResult
from ._history_common import load_merged_history
from ._rendering import render_jinja_template
from ..models import LEVELS, ScoreRecord
from ..query import compute_b30, find_song_scores, iter_history_score_events
from ..render import jinja_adapter
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"score", "\u5355\u66f2\u6210\u7ee9"}
_ORDER_BY = {"acc": "acc", "score": "score", "fc": "fc", "time": "update_at"}


@dataclass(slots=True)
class ScoreOptions:
    query: str
    rank: str | None = None
    unrank: bool = False
    order_by: str = "acc"


def _parse_options(args: str) -> ScoreOptions:
    text = args
    rank: str | None = None
    rank_match = re.search(r"-dif\s+(EZ|HD|IN|AT)", text, flags=re.IGNORECASE)
    if rank_match:
        rank = rank_match.group(1).upper()
        text = text.replace(rank_match.group(0), " ")

    unrank = bool(re.search(r"-unrank\b", text, flags=re.IGNORECASE))
    text = re.sub(r"-unrank\b", " ", text, flags=re.IGNORECASE)

    order_by = "acc"
    order_match = re.search(r"-or\s+(acc|score|fc|time)", text, flags=re.IGNORECASE)
    if order_match:
        order_by = _ORDER_BY[order_match.group(1).lower()]
        text = text.replace(order_match.group(0), " ")

    return ScoreOptions(query=" ".join(text.split()), rank=rank, unrank=unrank, order_by=order_by)


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    options = _parse_options(args)
    if not options.query:
        return CommandResult.text(render.render_need_query("score"))
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    song = ctx.searcher.best(options.query)
    if not song:
        return CommandResult.text(render.render_search(options.query, []))
    records = find_song_scores(snapshot, ctx.catalog, song)
    selected_rank = options.rank or _default_rank(records, song.charts)
    ranklist: dict[str, Any] | None = None
    ap_fc_count: dict[str, Any] | None = None
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        if not options.unrank:
            ranklist, ap_fc_count = await _load_online_score_data(ctx, user_id, song.id_with_suffix, selected_rank, options.order_by)
        history = await _load_score_history(ctx, user_id, song.id)
        template = "score/scoreOld" if ctx.config.score_image_version == "old" else "score/score"
        path = await render_jinja_template(
            ctx,
            template,
            jinja_adapter.score_data(
                ctx.paths,
                song,
                records,
                snapshot,
                b30_result=compute_b30(snapshot, ctx.catalog),
                history=history,
                ranklist=ranklist,
                selected_rank=selected_rank,
                ap_fc_count=ap_fc_count,
            ),
            "score",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_score(song, records))


async def _load_online_score_data(
    ctx: CommandContext,
    user_id: str,
    song_id: str,
    rank: str,
    order_by: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    try:
        ranklist = await ctx.client.fetch_score_ranklist_user(
            user_id,
            token=token,
            api_id=api_id,
            song_id=song_id,
            rank=rank,
            order_by=order_by,
        )
    except (SaveNotAvailable, RuntimeError, AttributeError):
        ranklist = None
    try:
        ap_fc_count = await ctx.client.fetch_song_ap_fc_count(song_id)
    except (SaveNotAvailable, RuntimeError, AttributeError):
        ap_fc_count = None
    return ranklist, ap_fc_count


async def _load_score_history(ctx: CommandContext, user_id: str, song_id: str) -> list[dict[str, Any]]:
    try:
        history = await load_merged_history(ctx, user_id, ["scoreHistory"])
    except (SaveNotAvailable, RuntimeError, AttributeError):
        return []
    events = [
        event for event in iter_history_score_events(history, ctx.catalog)
        if event.record.song_id == song_id
    ]
    events.sort(key=lambda item: item.date, reverse=True)
    return [
        {
            "rank": event.record.rank,
            "date_new": event.date.strftime("%Y/%m/%d"),
            "Rating": event.record.rating,
            "score_new": event.record.score,
            "acc_new": event.record.acc,
            "rks_new": event.record.rks,
        }
        for event in events[:16]
    ]


def _default_rank(records: list[ScoreRecord], charts: dict[str, Any]) -> str:
    if records:
        order = {rank: index for index, rank in enumerate(LEVELS)}
        return max(records, key=lambda record: order.get(record.rank, -1)).rank
    for rank in reversed(LEVELS):
        if rank in charts:
            return rank
    return "IN"
