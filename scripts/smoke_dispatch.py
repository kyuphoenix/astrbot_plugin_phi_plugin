from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, ROUTE_MODULES, dispatch
from phi_core.config import PluginConfig
from phi_core.data import SongSearcher, load_catalog
from phi_core.paths import PluginPaths
from phi_core.save import ApiBindResult, PgrTokenResult, PhiApiClient, SaveStore


class FakeLoginClient(PhiApiClient):
    async def bind_user(self, user_id: str, *, token=None, api_id=None, is_global=None):  # type: ignore[override]
        return ApiBindResult(api_id=str(api_id or "67890"), have_api_token=False)

    async def get_pgr_token(self, user_id: str, api_token: str):  # type: ignore[override]
        return PgrTokenResult(token="B" * 25, api_id="24680")


async def main() -> None:
    data_dir = ROOT / ".tmp_smoke_data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    try:
        paths = PluginPaths.from_root(ROOT, data_dir=data_dir)
        paths.ensure_data_dir()
        catalog = load_catalog(paths.info)
        config = PluginConfig(render_mode="text")
        ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )
        ctx.store.bind("smoke-user", "A" * 25, api_id="12345")

        cases = [
            ("help", "", "Phi Plugin Query Core"),
            ("song", "Glaciaxion", "Glaciaxion"),
            ("pgr", "", "还没有可用"),
            ("data", "", "还没有可用"),
            ("id", "", "查询 ID: 12345"),
            ("sessiontoken", "", "AAAA"),
            ("auth", "", "请提供查询平台 API Token"),
            ("best", "", "暂未"),
        ]
        for command, args, expected in cases:
            result = await dispatch(ctx, "smoke-user", command, args)
            if expected not in result.value:
                raise SystemExit(f"{command} expected {expected!r}, got {result.value!r}")
            print(f"{command}: {result.value.splitlines()[0]}")

        if ROUTE_MODULES.get("pgr") != "pgr":
            raise SystemExit(f"pgr route mismatch: {ROUTE_MODULES.get('pgr')}")

        image_ctx = CommandContext(
            config=PluginConfig(render_mode="image"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )
        image_result = await dispatch(image_ctx, "smoke-user", "help", "")
        if image_result.kind != "image" or not Path(image_result.value).exists():
            raise SystemExit(f"help image render failed: {image_result!r}")
        with Image.open(image_result.value) as rendered:
            if rendered.width < 1000 or rendered.height < 500:
                raise SystemExit(f"help image has unexpected size: {rendered.size}")

        login_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeLoginClient(config),
        )

        result = await dispatch(login_ctx, "login-user", "auth", "api-token-123")
        if "登录成功" not in result.value:
            raise SystemExit(f"auth expected success, got {result.value!r}")
        if login_ctx.store.get_token("login-user") != "B" * 25:
            raise SystemExit("auth did not persist returned sessionToken")
        if login_ctx.store.get_api_id("login-user") != "24680":
            raise SystemExit("auth did not persist returned api id")

        login_ctx.store.bind("bind-user", "A" * 25)
        result = await dispatch(login_ctx, "bind-user", "bind", "")
        if "查询 ID: 67890" not in result.value:
            raise SystemExit(f"bind existing token expected api id, got {result.value!r}")

        login_ctx.store.bind("api-user", "C" * 25)
        result = await dispatch(login_ctx, "api-user", "bind", "13579")
        if "查询 ID: 13579" not in result.value:
            raise SystemExit(f"bind api id expected success, got {result.value!r}")
        if login_ctx.store.get_token("api-user") is not None:
            raise SystemExit("bind api id did not clear stale token")

        print("dispatch smoke passed")
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)


if __name__ == "__main__":
    asyncio.run(main())
