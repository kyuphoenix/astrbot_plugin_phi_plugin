from __future__ import annotations

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ._sync import sync_save_with_progress
from ._notes import build_update_task_rows, load_notes, maybe_refresh_daily_tasks, parse_datetime
from ..render import jinja_adapter
from ..render import text as render
from ..query.progress import format_datetime
from ..save import SaveNotAvailable

ALIASES = {"update", "更新存档"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        return CommandResult.text(render.render_not_bound())
    try:
        result = await sync_save_with_progress(ctx, user_id)
        if ctx.config.render_mode == "image" and ctx.html_render is not None:
            notes_data = load_notes(ctx, user_id)
            await maybe_refresh_daily_tasks(ctx, user_id, result.snapshot, notes_data)
            notes_data = load_notes(ctx, user_id)
            path = await render_jinja_template(
                ctx,
                "update/update",
                jinja_adapter.update_data(
                    ctx.paths,
                    result.progress,
                    history=ctx.store.load_history(user_id),
                    task_data=build_update_task_rows(ctx, result.snapshot, notes_data),
                    task_time=_format_task_time(notes_data.get("task_time")),
                    notes=_as_int(notes_data.get("money")),
                    theme=str(notes_data.get("theme") or "default"),
                ),
                "update",
                width=800,
            )
            return CommandResult.image(path)
        return CommandResult.text(render.render_update_progress(result.progress))
    except SaveNotAvailable as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))
    except Exception as exc:
        return CommandResult.text(render.render_update_failed(str(exc)))


def _format_task_time(value: object) -> str:
    parsed = parse_datetime(value)
    return format_datetime(parsed) if parsed is not None else str(value or "")


def _as_int(value: object) -> int:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
