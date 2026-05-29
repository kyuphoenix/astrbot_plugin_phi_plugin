from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from .common import CommandContext, CommandResult
from . import b30, bind, clean, help, ill, info, rand, score, search, song, unbind, update
from ..render import text as render

CommandHandler = Callable[[CommandContext, str, str], CommandResult | Awaitable[CommandResult]]

_MODULES = [
    help,
    song,
    search,
    rand,
    ill,
    bind,
    unbind,
    clean,
    update,
    b30,
    score,
    info,
]

ROUTES: dict[str, CommandHandler] = {}
for module in _MODULES:
    for alias in module.ALIASES:
        ROUTES[alias.casefold()] = module.handle


async def dispatch(ctx: CommandContext, user_id: str, command: str, args: str) -> CommandResult:
    handler = ROUTES.get(command.casefold())
    if handler is None:
        return CommandResult.text(render.render_unsupported(f"phi {command}"))
    result = handler(ctx, user_id, args)
    if inspect.isawaitable(result):
        return await result
    return result


__all__ = ["CommandContext", "CommandResult", "ROUTES", "dispatch"]
