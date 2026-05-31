from __future__ import annotations

from ._notes import apply_task_rewards, build_sign_panel_data, build_tasks_panel_data, load_notes, maybe_refresh_daily_tasks
from ._rendering import render_jinja_template
from .common import CommandContext, CommandResult
from ..render import jinja_adapter
from ..render import text as render

ALIASES = {"task", "tasks", "我的任务"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    notes = load_notes(ctx, user_id)
    added = apply_task_rewards(ctx, user_id, snapshot, notes)
    refreshed = await maybe_refresh_daily_tasks(ctx, user_id, snapshot, notes)
    if added:
        save_notes(ctx, user_id, notes)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        sign_data = build_sign_panel_data(ctx, user_id, snapshot, notes)
        return CommandResult.image(await render_jinja_template(ctx, "sign/sign", jinja_adapter.sign_data(ctx.paths, sign_data), "task", width=2048))
    data = build_tasks_panel_data(
        ctx,
        user_id,
        snapshot,
        notes,
        change_notes=added,
        tips="今天还没有任务，已自动生成一组。" if refreshed else "",
    )
    return CommandResult.text(_text_tasks(data, added=added))


def _text_tasks(data: dict, *, added: int = 0) -> str:
    lines = [f"Phi-Plugin 任务列表 | Notes: {data.get('Notes', 0)}"]
    if added:
        lines.append(f"刚刚完成任务获得 +{added} Notes。")
    tasks = data.get("task") if isinstance(data.get("task"), list) else []
    if not any(tasks):
        lines.append("暂无任务，可以使用 phi sign 或 phi retask 生成。")
        return "\n".join(lines)
    for index, task in enumerate(tasks, 1):
        if not isinstance(task, dict):
            continue
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        done = "已完成" if task.get("finished") else "未完成"
        lines.append(
            f"{index}. {task.get('song')} [{request.get('rank')}] "
            f"{str(request.get('type', 'acc')).upper()} {request.get('value')} "
            f"+{task.get('reward', 0)} Notes | {done}"
        )
    return "\n".join(lines)
