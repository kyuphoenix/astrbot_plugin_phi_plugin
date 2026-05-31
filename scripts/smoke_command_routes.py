from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import ROUTE_MODULES, ROUTES, dispatch
from phi_core.commands.common import CommandContext
from phi_core.config import PluginConfig
from phi_core.paths import PluginPaths


EXPECTED_ROUTES = {
    "help": "help",
    "song": "song",
    "search": "search",
    "rand": "rand",
    "ill": "ill",
    "auth": "auth",
    "bind": "bind",
    "cnbind": "cnbind",
    "gbbind": "gbbind",
    "unbind": "unbind",
    "clean": "clean",
    "update": "update",
    "b30": "b30",
    "rks": "rks",
    "pgr": "pgr",
    "score": "score",
    "info": "info",
    "info1": "info1",
    "info2": "info2",
    "data": "data",
    "id": "id",
    "sessiontoken": "sessiontoken",
    "best": "best",
    "p30": "p30",
    "fc30": "fc30",
    "x30": "x30",
    "lmtacc": "lmtacc",
    "suggest": "suggest",
    "tips": "tips",
    "alias": "alias",
    "com": "com",
    "table": "table",
    "newlog": "newlog",
    "newnotice": "newnotice",
    "randclg": "randclg",
    "chap": "chap",
    "achievement": "achievement",
    "lvscore": "lvscore",
    "list": "list",
    "hisb30": "hisb30",
    "renderdiag": "renderdiag",
    "setapitoken": "setapitoken",
    "tokenlist": "tokenlist",
    "tkls": "tokenlist",
    "lstk": "tokenlist",
}


def main() -> None:
    missing = {alias: module for alias, module in EXPECTED_ROUTES.items() if ROUTE_MODULES.get(alias) != module}
    if missing:
        raise SystemExit(f"route mismatch: {missing}")

    command_dir = Path(__file__).resolve().parents[1] / "phi_core" / "commands"
    public_modules = sorted(
        item.stem
        for item in command_dir.glob("*.py")
        if not item.stem.startswith("_") and item.stem not in {"__init__", "common"}
    )
    unregistered = [name for name in public_modules if name not in set(ROUTE_MODULES.values())]
    if unregistered:
        raise SystemExit(f"unregistered command modules: {unregistered}")

    for alias, module_name in ROUTE_MODULES.items():
        module = importlib.import_module(f"phi_core.commands.{module_name}")
        if not hasattr(module, "handle"):
            raise SystemExit(f"{alias} -> {module_name} has no handle")
        if alias not in ROUTES:
            raise SystemExit(f"{alias} missing from ROUTES")

    class DynamicCtx(CommandContext):
        pass

    called: list[tuple[str, str, str]] = []
    original_p30 = ROUTES["p30"]

    def fake_p30(ctx, user_id, args):
        called.append((user_id, "p30", args))
        from phi_core.commands.common import CommandResult
        return CommandResult.text("ok")

    ROUTES["p30"] = fake_p30
    try:
        import asyncio

        ctx = DynamicCtx(
            config=PluginConfig(render_mode="text"),
            paths=PluginPaths.from_root(ROOT),
            catalog=None,  # type: ignore[arg-type]
            searcher=None,  # type: ignore[arg-type]
            store=None,  # type: ignore[arg-type]
            client=None,  # type: ignore[arg-type]
        )
        asyncio.run(dispatch(ctx, "dynamic-user", "p45", "extra"))
    finally:
        ROUTES["p30"] = original_p30
    if called != [("dynamic-user", "p30", "45 extra")]:
        raise SystemExit(f"dynamic pN dispatch did not forward limit to p30: {called!r}")

    print(f"command route smoke passed: {len(public_modules)} modules, {len(ROUTES)} aliases")


if __name__ == "__main__":
    main()
