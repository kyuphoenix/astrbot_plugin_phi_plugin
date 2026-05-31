from __future__ import annotations

from ._notes import build_sign_panel_data, build_tasks_panel_data, day_start, load_notes, maybe_refresh_daily_tasks, parse_datetime, save_notes
from ._rendering import render_jinja_template
from .common import CommandContext, CommandResult
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"retask", "刷新任务"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())

    notes = load_notes(ctx, user_id)
    last_task = parse_datetime(notes.get("task_time"))
    change_notes = 0
    free_refresh = last_task is None or last_task < day_start()
    if not free_refresh:
        if int(notes.get("money") or 0) < 20:
            return CommandResult.text(f"刷新任务需要 20 Notes，你当前的 Note 数量为：{notes.get('money', 0)}")
        notes["money"] = int(notes.get("money") or 0) - 20
        change_notes = -20
        save_notes(ctx, user_id, notes)

    await maybe_refresh_daily_tasks(ctx, user_id, snapshot, notes, force=True, preserve_finished=not free_refresh)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        sign_data = build_sign_panel_data(ctx, user_id, snapshot, notes)
        return CommandResult.image(await render_jinja_template(ctx, "sign/sign", jinja_adapter.sign_data(ctx.paths, sign_data), "retask", width=2048))
    data = build_tasks_panel_data(
        ctx,
        user_id,
        snapshot,
        notes,
        change_notes=change_notes,
        tips="每日首次刷新免费。" if free_refresh else "本次刷新消耗 20 Notes。",
    )
    return CommandResult.text(f"任务已刷新。当前 Notes：{notes.get('money', 0)}")
