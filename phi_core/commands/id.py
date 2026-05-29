from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"id", "apiid", "uid", "查询id"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    snapshot = ctx.load_snapshot(user_id)
    player_id = snapshot.player_id if snapshot else ""
    player_name = snapshot.player_name if snapshot else ""
    return CommandResult.text(render.render_id_info(
        ctx.store.get_api_id(user_id),
        player_id=player_id,
        player_name=player_name,
    ))
