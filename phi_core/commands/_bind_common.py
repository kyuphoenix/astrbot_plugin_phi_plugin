from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render
from ..save import StoreError


def bind_token(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    token = args.strip().split()[0] if args.strip() else ""
    try:
        ctx.store.bind(user_id, token)
    except StoreError as exc:
        return CommandResult.text(str(exc))
    return CommandResult.text(render.render_bind_ok())
