from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import ROUTE_MODULES, ROUTES


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
    "data": "data",
    "id": "id",
    "sessiontoken": "sessiontoken",
    "best": "best",
    "suggest": "suggest",
    "chap": "chap",
    "achievement": "achievement",
    "lvscore": "lvscore",
    "list": "list",
    "hisb30": "hisb30",
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

    print(f"command route smoke passed: {len(public_modules)} modules, {len(ROUTES)} aliases")


if __name__ == "__main__":
    main()
