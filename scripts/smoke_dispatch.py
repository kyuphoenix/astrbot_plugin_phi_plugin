from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, ROUTE_MODULES, dispatch
from phi_core.config import PluginConfig
from phi_core.data import SongSearcher, load_catalog
from phi_core.paths import PluginPaths
from phi_core.save import PhiApiClient, SaveStore


async def main() -> None:
    data_dir = ROOT / ".tmp_smoke_data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    try:
        paths = PluginPaths.from_root(ROOT, data_dir=data_dir)
        paths.ensure_data_dir()
        catalog = load_catalog(paths.info)
        config = PluginConfig()
        ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )

        cases = [
            ("help", "", "Phi Plugin Query Core"),
            ("song", "Glaciaxion", "Glaciaxion"),
            ("pgr", "", "还没有可用"),
            ("data", "", "还没有可用"),
            ("best", "", "暂未"),
        ]
        for command, args, expected in cases:
            result = await dispatch(ctx, "smoke-user", command, args)
            if expected not in result.value:
                raise SystemExit(f"{command} expected {expected!r}, got {result.value!r}")
            print(f"{command}: {result.value.splitlines()[0]}")

        if ROUTE_MODULES.get("pgr") != "pgr":
            raise SystemExit(f"pgr route mismatch: {ROUTE_MODULES.get('pgr')}")

        print("dispatch smoke passed")
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)


if __name__ == "__main__":
    asyncio.run(main())
