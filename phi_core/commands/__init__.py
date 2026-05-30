from __future__ import annotations

import importlib
import inspect
from collections.abc import Awaitable, Callable
from pkgutil import iter_modules

from .common import CommandContext, CommandResult
from ..render import text as render

CommandHandler = Callable[[CommandContext, str, str], CommandResult | Awaitable[CommandResult]]

_SKIP_MODULES = {"common"}


def _load_command_modules():
    modules = []
    for module_info in iter_modules(__path__):  # type: ignore[name-defined]
        name = module_info.name
        if name.startswith("_") or name in _SKIP_MODULES:
            continue
        module = importlib.import_module(f"{__name__}.{name}")
        if hasattr(module, "ALIASES") and hasattr(module, "handle"):
            modules.append(module)
    return sorted(modules, key=lambda module: module.__name__)


ROUTES: dict[str, CommandHandler] = {}
ROUTE_MODULES: dict[str, str] = {}
for module in _load_command_modules():
    for alias in module.ALIASES:
        normalized = str(alias).casefold()
        ROUTES[normalized] = module.handle
        ROUTE_MODULES[normalized] = module.__name__.rsplit(".", 1)[-1]


async def dispatch(ctx: CommandContext, user_id: str, command: str, args: str) -> CommandResult:
    handler = ROUTES.get(command.casefold())
    if handler is None:
        return CommandResult.text(render.render_unsupported(f"phi {command}"))
    result = handler(ctx, user_id, args)
    if inspect.isawaitable(result):
        return await result
    return result


__all__ = [
    "CommandContext",
    "CommandResult",
    "ROUTES",
    "ROUTE_MODULES",
    "dispatch",
]
