from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..data import latest_version_log, load_version_log, resolve_version_code
from ..query import charts_for_table, compute_achievement_rows, compute_achievement_rows_for_charts, iter_score_records
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"achievement", "ahv"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    match = re.search(r"\d+", args)
    if not match:
        return CommandResult.text("\u8bf7\u8f93\u5165\u5b9a\u6570\u6574\u6570\u3002\n\u683c\u5f0f\uff1aphi achievement <\u5b9a\u6570\u6574\u6570>")
    difficulty_floor = int(match.group(0))
    if difficulty_floor < 1:
        return CommandResult.text("\u5b9a\u6570\u4e0d\u80fd\u5c0f\u4e8e 1\u3002")
    version_label = "current"
    version_changes = None
    version_match = re.search(r"-v\s*(\S+)", args, flags=re.IGNORECASE)
    if version_match:
        version_code = resolve_version_code(ctx.paths.info, version_match.group(1))
        version_log = load_version_log(ctx.paths.info, version_code) if version_code is not None else None
        if version_log is None:
            return CommandResult.text(f"\u672a\u627e\u5230\u7248\u672c {version_match.group(1)} \u7684\u672c\u5730\u4fe1\u606f\u3002")
        version_label = version_log.version_label
        version_changes = version_log.changes
    else:
        latest = latest_version_log(ctx.paths.info)
        if latest is not None:
            version_label = latest.version_label
            version_changes = latest.changes

    if version_changes is not None:
        charts = charts_for_table(ctx.catalog, difficulty_floor, version_changes)
        rows = compute_achievement_rows_for_charts(iter_score_records(snapshot, ctx.catalog), charts, difficulty_floor)
    else:
        charts = charts_for_table(ctx.catalog, difficulty_floor)
        rows = compute_achievement_rows(iter_score_records(snapshot, ctx.catalog), ctx.catalog, difficulty_floor)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        record_map = {
            (record.song_id, record.rank): record
            for record in iter_score_records(snapshot, ctx.catalog)
        }
        path = await render_jinja_template(
            ctx,
            "table/table",
            jinja_adapter.table_data(
                ctx.paths,
                charts,
                difficulty=difficulty_floor,
                version_label=version_label,
                title_dec="Player Achievements",
                record_map=record_map,
                snapshot=snapshot,
            ),
            "achievement",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_achievement(rows, difficulty_floor))
