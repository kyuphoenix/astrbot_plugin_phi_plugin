from __future__ import annotations

import importlib
import inspect
import re
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
    normalized_command = command.casefold()
    handler = ROUTES.get(normalized_command)
    dynamic_args = args
    if handler is None:
        dynamic = _dynamic_score_command(normalized_command)
        if dynamic is not None:
            normalized_command, limit_text = dynamic
            handler = ROUTES.get(normalized_command)
            dynamic_args = f"{limit_text} {args}".strip()
    if handler is None:
        return CommandResult.text(render.render_unsupported(f"phi {command}"))
    previous_user_id = ctx.current_user_id
    ctx.current_user_id = user_id
    try:
        result = handler(ctx, user_id, dynamic_args)
        if inspect.isawaitable(result):
            return await result
        return result
    finally:
        ctx.current_user_id = previous_user_id


def _dynamic_score_command(command: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"arcgrosb(\d+)", command)
    if match:
        return "arcgros", match.group(1)
    match = re.fullmatch(r"(fc|p|x)(\d+)", command)
    if match:
        prefix, limit_text = match.groups()
        return f"{prefix}30", limit_text
    match = re.fullmatch(r"b(\d+)", command)
    if match:
        return "b30", match.group(1)
    return None


__all__ = [
    "CommandContext",
    "CommandResult",
    "ROUTES",
    "ROUTE_MODULES",
    "dispatch",
]
