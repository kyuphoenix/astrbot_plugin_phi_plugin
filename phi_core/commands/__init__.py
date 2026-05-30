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


def command_alias_groups() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for alias, module_name in ROUTE_MODULES.items():
        grouped.setdefault(module_name, []).append(alias)
    return {module_name: sorted(aliases) for module_name, aliases in sorted(grouped.items())}


def render_toolset_catalog() -> str:
    lines = [
        "Phi Plugin 已注册命令工具集：",
        "调用 phi_plugin 时，command 填下面任意命令/别名，args 填原命令后面的参数。",
    ]
    for module_name, aliases in command_alias_groups().items():
        preferred = module_name if module_name in aliases else aliases[0]
        alias_text = ", ".join(alias for alias in aliases if alias != preferred)
        if alias_text:
            lines.append(f"- {preferred}: {alias_text}")
        else:
            lines.append(f"- {preferred}")
    return "\n".join(lines)


__all__ = [
    "CommandContext",
    "CommandResult",
    "ROUTES",
    "ROUTE_MODULES",
    "command_alias_groups",
    "dispatch",
    "render_toolset_catalog",
]
