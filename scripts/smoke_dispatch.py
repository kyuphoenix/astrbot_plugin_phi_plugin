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
from phi_core.save import ApiBindResult, PgrTokenResult, PhiApiClient, SaveStore, TapTapLoginResult, TapTapQrLogin, TapTapQrRequest


class FakeLoginClient(PhiApiClient):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.bind_calls: list[dict[str, object | None]] = []

    async def bind_user(self, user_id: str, *, token=None, api_id=None, is_global=None):  # type: ignore[override]
        self.bind_calls.append({"user_id": user_id, "token": token, "api_id": api_id, "is_global": is_global})
        return ApiBindResult(api_id=str(api_id or "67890"), have_api_token=False)

    async def get_pgr_token(self, user_id: str, api_token: str):  # type: ignore[override]
        return PgrTokenResult(token="B" * 25, api_id="24680")


class FakeTapTapLogin(TapTapQrLogin):
    def __init__(self, config: PluginConfig, paths: PluginPaths):
        super().__init__(config, paths)
        self.request_use_global: bool | None = None
        self.wait_use_global: bool | None = None

    async def request_qrcode(self, *, use_global: bool = False):  # type: ignore[override]
        self.request_use_global = use_global
        return TapTapQrRequest(
            device_id="device",
            device_code="code",
            qrcode_url="https://example.com/qrcode",
            expires_in=120,
            interval=1,
            raw={},
        )

    async def wait_for_session_token(self, request: TapTapQrRequest, *, use_global: bool = False, on_scanned=None):  # type: ignore[override]
        self.wait_use_global = use_global
        if on_scanned is not None:
            maybe_awaitable = on_scanned()
            if maybe_awaitable is not None:
                await maybe_awaitable
        return TapTapLoginResult(session_token="D" * 25, raw={})


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

        login_client = FakeLoginClient(config)
        login_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=login_client,
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
        if login_client.bind_calls[-1]["is_global"] is not False:
            raise SystemExit(f"bind did not apply default global flag: {login_client.bind_calls[-1]!r}")

        default_global_client = FakeLoginClient(PluginConfig(default_global=True, render_mode="text"))
        default_global_ctx = CommandContext(
            config=default_global_client.config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=default_global_client,
        )
        default_global_ctx.store.bind("gb-default-user", "E" * 25)
        await dispatch(default_global_ctx, "gb-default-user", "bind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not True:
            raise SystemExit(f"bind did not use configured global default: {default_global_client.bind_calls[-1]!r}")

        await dispatch(default_global_ctx, "gb-default-user", "cnbind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not False:
            raise SystemExit(f"cnbind did not force CN endpoint: {default_global_client.bind_calls[-1]!r}")

        await dispatch(default_global_ctx, "gb-default-user", "gbbind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not True:
            raise SystemExit(f"gbbind did not force global endpoint: {default_global_client.bind_calls[-1]!r}")

        login_ctx.store.bind("api-user", "C" * 25)
        result = await dispatch(login_ctx, "api-user", "bind", "13579")
        if "查询 ID: 13579" not in result.value:
            raise SystemExit(f"bind api id expected success, got {result.value!r}")
        if login_ctx.store.get_token("api-user") is not None:
            raise SystemExit("bind api id did not clear stale token")

        sent: list[CommandResult] = []

        async def capture(result: CommandResult) -> None:
            sent.append(result)

        taptap = FakeTapTapLogin(config, paths)
        qrcode_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeLoginClient(config),
            taptap=taptap,
            sender=capture,
        )
        result = await dispatch(qrcode_ctx, "qr-user", "bind", "qrcode")
        if "TapTap 二维码登录已完成" not in result.value:
            raise SystemExit(f"qrcode bind expected completion, got {result.value!r}")
        if qrcode_ctx.store.get_token("qr-user") != "D" * 25:
            raise SystemExit("qrcode bind did not persist returned sessionToken")
        if len(sent) != 3 or sent[0].kind != "image" or sent[1].kind != "text" or sent[2].kind != "text":
            raise SystemExit(f"qrcode bind did not emit qr image, hint, and scanned notice: {sent!r}")
        if "二维码已扫描" not in sent[2].value:
            raise SystemExit(f"qrcode bind did not emit scanned notice: {sent!r}")
        if taptap.request_use_global is not False or taptap.wait_use_global is not False:
            raise SystemExit(f"qrcode bind did not use default endpoint: {taptap.request_use_global}, {taptap.wait_use_global}")
        if not Path(sent[0].value).exists():
            raise SystemExit("qrcode image was not created")

        print("dispatch smoke passed")
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)


if __name__ == "__main__":
    asyncio.run(main())
