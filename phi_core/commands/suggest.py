from __future__ import annotations

from typing import Any

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ._b30_common import _api_song_id, _lookup_avg, _rks_range
from ._user_settings import normalize_settings
from ..models import ChartEntry, LEVELS, PhiSuggestEntry, SaveSnapshot, ScoreRecord
from ..query import all_chart_entries, compute_b30, records_by_chart, suggest_entries
from ..query.filters import parse_score_filter
from ..render import jinja_adapter
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"suggest", "\u63a8\u5206", "\u63a8\u5206\u5efa\u8bae"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    score_filter = parse_score_filter(args, max_difficulty=_max_difficulty(ctx))
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        avg_lookup: dict[tuple[str, str], float] = {}
        phi_entries: list[PhiSuggestEntry] = []
        if _allow_api(ctx, user_id):
            avg_lookup, phi_entries = await _load_online_suggest_data(ctx, snapshot)
        entries = suggest_entries(snapshot, ctx.catalog, score_filter=score_filter, avg_lookup=avg_lookup)
        path = await render_jinja_template(
            ctx,
            "suggest/suggest",
            jinja_adapter.suggest_data(ctx.paths, entries, phi_entries=phi_entries),
            "suggest",
        )
        return CommandResult.image(path)
    entries = suggest_entries(snapshot, ctx.catalog, score_filter=score_filter)
    return CommandResult.text(render.render_suggest(entries))


def _max_difficulty(ctx: CommandContext) -> float:
    return max((entry.difficulty for entry in all_chart_entries(ctx.catalog)), default=18.0)


def _allow_api(ctx: CommandContext, user_id: str) -> bool:
    return normalize_settings(ctx.store.load_user_settings(user_id)).get("allowApiUsage") is not False


async def _load_online_suggest_data(
    ctx: CommandContext,
    snapshot: SaveSnapshot,
) -> tuple[dict[tuple[str, str], float], list[PhiSuggestEntry]]:
    result = compute_b30(snapshot, ctx.catalog, limit=1000)
    min_rks, max_rks = _rks_range(result.computed_rks)
    song_ids = sorted({_api_song_id(song.id) for song in ctx.catalog.all_songs()})
    record_map = records_by_chart(snapshot, ctx.catalog)

    avg_lookup: dict[tuple[str, str], float] = {}
    try:
        avg_data = await ctx.client.fetch_all_song_acc_avg(song_ids, min_rks=min_rks, max_rks=max_rks, b30=True)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        avg_data = {}
    if isinstance(avg_data, dict):
        avg_lookup = _build_avg_lookup(ctx, snapshot, avg_data)

    phi_entries: list[PhiSuggestEntry] = []
    try:
        apfc_data = await ctx.client.fetch_songs_ap_fc_count(song_ids, ranks=list(LEVELS), min_rks=min_rks, max_rks=max_rks)
    except (SaveNotAvailable, AttributeError, RuntimeError):
        apfc_data = {}
    if isinstance(apfc_data, dict):
        phi_entries = _build_phi_entries(ctx, apfc_data, result.phi_records, record_map)
    return avg_lookup, phi_entries


def _build_avg_lookup(ctx: CommandContext, snapshot: SaveSnapshot, data: dict[str, Any]) -> dict[tuple[str, str], float]:
    record_map = records_by_chart(snapshot, ctx.catalog)
    lookup: dict[tuple[str, str], float] = {}
    for song in ctx.catalog.all_songs():
        for rank in LEVELS:
            if rank not in song.charts:
                continue
            avg = _lookup_avg(data, song.id, rank)
            if avg is None:
                continue
            current = record_map.get((song.id, rank))
            if avg > (current.acc if current else 0.0):
                lookup[(song.id, rank)] = avg
    return lookup


def _build_phi_entries(
    ctx: CommandContext,
    data: dict[str, Any],
    phi_records: list[ScoreRecord],
    record_map: dict[tuple[str, str], ScoreRecord],
) -> list[PhiSuggestEntry]:
    entries: list[PhiSuggestEntry] = []
    third_phi_difficulty = phi_records[2].difficulty if len(phi_records) >= 3 else None
    for raw_song_id, raw_ranks in data.items():
        song = ctx.catalog.get(str(raw_song_id))
        if song is None or not isinstance(raw_ranks, dict):
            continue
        for rank in LEVELS:
            chart = song.charts.get(rank)
            raw_count = raw_ranks.get(rank)
            if chart is None or chart.difficulty is None or not isinstance(raw_count, dict):
                continue
            if third_phi_difficulty is not None and chart.difficulty <= third_phi_difficulty:
                continue
            current = record_map.get((song.id, rank))
            if current is not None and current.score >= 1_000_000:
                continue
            ap_count = _as_int(raw_count.get("apCount"))
            if ap_count <= 0:
                continue
            entries.append(PhiSuggestEntry(
                chart=ChartEntry(
                    song_id=song.id,
                    song_title=song.title,
                    rank=rank,
                    difficulty=float(chart.difficulty),
                    difficulty_text=chart.difficulty_text or f"{chart.difficulty:.1f}",
                    combo=chart.combo,
                ),
                ap_count=ap_count,
                fc_count=_as_int(raw_count.get("fcCount")),
                total=_as_int(raw_count.get("total")),
            ))
    return sorted(entries, key=lambda entry: (-entry.ap_count, -entry.chart.difficulty, entry.chart.song_title))[:3]


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
