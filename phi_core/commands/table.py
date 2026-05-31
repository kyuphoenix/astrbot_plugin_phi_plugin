from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ._rendering import render_original_html
from ..data import load_version_log, resolve_version_code
from ..query import charts_for_table, iter_score_records
from ..render import original
from ..render import text as render

ALIASES = {"table", "\u5b9a\u6570\u8868"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    match = re.search(r"\d+(?:\.\d+)?", args)
    if not match:
        return CommandResult.text("\u8bf7\u8f93\u5165\u5b9a\u6570\u3002\n\u683c\u5f0f\uff1aphi table <\u5b9a\u6570>")
    difficulty = float(match.group(0))
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
    charts = charts_for_table(ctx.catalog, difficulty, version_changes)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        snapshot = ctx.load_snapshot(user_id)
        record_map = {(record.song_id, record.rank): record for record in iter_score_records(snapshot, ctx.catalog)} if snapshot else {}
        path = await render_original_html(
            ctx,
            original.table_with_records_html(
                ctx.paths,
                charts,
                difficulty=difficulty,
                version_label=version_label,
                record_map=record_map,
                snapshot=snapshot,
            ),
            "table",
        )
        return CommandResult.image(path)
    return CommandResult.text(render.render_table(difficulty, charts, version_label=version_label))
