from __future__ import annotations

from typing import Any

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"data"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    if not snapshot:
        return CommandResult.text(render.render_no_cached_save())
    money = _extract_money(snapshot.raw)
    if money is None:
        return CommandResult.text(render.render_missing_data())
    return CommandResult.text(render.render_data(money))


def _extract_money(raw: dict[str, Any]) -> list[int] | None:
    game_progress = raw.get("gameProgress")
    money = game_progress.get("money") if isinstance(game_progress, dict) else raw.get("money")
    if not isinstance(money, list):
        return None

    values: list[int] = []
    for item in money[:5]:
        try:
            values.append(int(item))
        except (TypeError, ValueError):
            values.append(0)
    while len(values) < 5:
        values.append(0)
    return values
