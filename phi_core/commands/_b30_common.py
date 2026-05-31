from __future__ import annotations

import math
import re

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..query import compute_b30
from ..render import jinja_adapter
from ..render import text as render
from ..save.codec import SaveNotAvailable


def _rks_range(rks: float) -> tuple[float, float]:
    return (
        math.floor((rks - 0.05) / 0.05) * 0.05,
        math.floor((rks + 0.05) / 0.05) * 0.05,
    )


def _rks_range_up(rks: float) -> tuple[float, float]:
    return (
        (math.floor((rks - 0.05) / 0.05) + 2) * 0.05,
        (math.floor((rks + 0.05) / 0.05) + 3) * 0.05,
    )


def _api_song_id(song_id: str) -> str:
    return song_id if song_id.endswith(".0") else f"{song_id}.0"


def _lookup_avg(data: dict, song_id: str, rank: str) -> float | None:
    for candidate in (song_id, _api_song_id(song_id), song_id.removesuffix(".0")):
        raw_song = data.get(candidate)
        if not isinstance(raw_song, dict):
            continue
        raw_rank = raw_song.get(rank)
        if not isinstance(raw_rank, dict):
            continue
        value = raw_rank.get("accAvg")
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None
    return None


async def _attach_acc_averages(ctx: CommandContext, result) -> None:
    records = result.records
    if not records:
        return
    song_ids = sorted({_api_song_id(record.song_id) for record in records if record.rank != "LEGACY"})
    min_rks, max_rks = _rks_range(result.computed_rks)
    try:
        data = await ctx.client.fetch_all_song_acc_avg(song_ids, min_rks=min_rks, max_rks=max_rks)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        return

    all_higher = True
    for index, record in enumerate(records):
        if index >= 27 and all_higher:
            break
        avg = _lookup_avg(data, record.song_id, record.rank)
        if avg is None:
            continue
        record.acc_avg = avg
        if record.acc < avg:
            all_higher = False
            record.acc_kind = "Lower"
        else:
            record.acc_kind = "Higher"

    if not all_higher:
        return

    min_rks, max_rks = _rks_range_up(result.computed_rks)
    try:
        data = await ctx.client.fetch_all_song_acc_avg(song_ids, min_rks=min_rks, max_rks=max_rks)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        return
    for record in records:
        avg = _lookup_avg(data, record.song_id, record.rank)
        if avg is None:
            continue
        record.acc_avg = avg
        if record.acc < avg:
            all_higher = False
            record.acc_kind = "Hyper"
        else:
            record.acc_kind = "Finished"


async def render_best30(ctx: CommandContext, user_id: str, args: str = "") -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    requested_limit = _limit_from_args(args)
    limit = max(33, requested_limit or ctx.config.max_b30)
    result = compute_b30(snapshot, ctx.catalog, limit=limit)
    await _attach_acc_averages(ctx, result)
    if ctx.config.render_mode == "image":
        path = await render_jinja_template(ctx, "b19/b19", jinja_adapter.b30_data(ctx.paths, result, snapshot), "b30")
        return CommandResult.image(path)
    return CommandResult.text(render.render_b30(result, limit=limit))


def _limit_from_args(args: str) -> int | None:
    match = re.search(r"\d+", args or "")
    if not match:
        return None
    return max(1, min(100, int(match.group(0))))
