from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    if not re.search(r"@filter\.command_group\(\s*['\"]phi['\"](?:\s*,|\s*\))", source):
        raise SystemExit("phi commands should be registered as an AstrBot command_group")
    if "@filter.llm_tool" in source:
        raise SystemExit("phi commands should not be registered as llm tools")
    if '@filter.command("pgr"' not in source:
        raise SystemExit("top-level pgr shortcut should remain registered")

    from phi_core.commands import ROUTE_MODULES

    modules = set(ROUTE_MODULES.values())
    registered = set(re.findall(r"@phi\.command\('([^']+)'", source))
    missing = []
    for module_name in modules:
        aliases = {alias for alias, module in ROUTE_MODULES.items() if module == module_name}
        preferred = module_name if module_name in aliases else sorted(aliases)[0]
        if preferred not in registered:
            missing.append(preferred)
    if missing:
        raise SystemExit(f"missing command_group subcommands: {missing}")

    print(f"command group smoke passed: {len(modules)} subcommands")


if __name__ == "__main__":
    main()
