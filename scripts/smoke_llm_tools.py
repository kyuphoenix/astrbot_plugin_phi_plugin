from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    required_snippets = [
        '@filter.llm_tool(name="phi_plugin")',
        '@filter.llm_tool(name="phi_plugin_commands")',
        "render_toolset_catalog",
        'render_mode="text"',
        "render_text_as_image=False",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in source]
    if missing:
        raise SystemExit(f"missing llm tool registration snippets: {missing}")

    from phi_core.commands import ROUTES, command_alias_groups, render_toolset_catalog

    groups = command_alias_groups()
    if not groups:
        raise SystemExit("command alias groups should not be empty")
    for alias in ["pgr", "b30", "bind", "update", "down"]:
        if alias not in ROUTES:
            raise SystemExit(f"{alias} should be available to the phi_plugin tool")
    catalog = render_toolset_catalog()
    for text in ["phi_plugin", "pgr", "bind", "down"]:
        if text not in catalog:
            raise SystemExit(f"toolset catalog missing {text!r}")

    print(f"llm tool smoke passed: {len(groups)} command modules, {len(ROUTES)} aliases")


if __name__ == "__main__":
    main()
