from __future__ import annotations

import asyncio
import sys
import tempfile
import types
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
astrbot_root = PROJECT_ROOT / "AstrBot"
if astrbot_root.exists() and str(astrbot_root) not in sys.path:
    sys.path.insert(0, str(astrbot_root))


def _install_astrbot_stubs() -> None:
    astrbot = types.ModuleType("astrbot")
    astrbot_api = types.ModuleType("astrbot.api")
    astrbot_api_all = types.ModuleType("astrbot.api.all")
    astrbot_api_event = types.ModuleType("astrbot.api.event")
    astrbot_api_event_filter = types.ModuleType("astrbot.api.event.filter")
    astrbot_api_message_components = types.ModuleType("astrbot.api.message_components")
    astrbot_api_star = types.ModuleType("astrbot.api.star")

    class FakeLogger:
        def info(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

    class FakeStar:
        def __init__(self, *args, **kwargs):
            pass

    class FakeStarTools:
        @staticmethod
        def get_data_dir(_name: str) -> str:
            return tempfile.gettempdir()

    def identity_decorator(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    class FakeCommandGroup:
        def command(self, *_args, **_kwargs):
            return identity_decorator()

    class FakeCustomFilter:
        pass

    def command_group(*_args, **_kwargs):
        def decorator(_func):
            return FakeCommandGroup()

        return decorator

    astrbot_api_all.AstrBotConfig = dict
    astrbot_api_all.logger = FakeLogger()
    astrbot_api_event.AstrMessageEvent = object
    astrbot_api_event_filter.command = identity_decorator
    astrbot_api_event_filter.command_group = command_group
    astrbot_api_event_filter.CustomFilter = FakeCustomFilter
    astrbot_api_event_filter.EventMessageType = types.SimpleNamespace(ALL=object())
    astrbot_api_event_filter.event_message_type = identity_decorator
    astrbot_api_event_filter.custom_filter = identity_decorator
    astrbot_api_message_components.Image = FakeImageComponent
    astrbot_api_star.Context = object
    astrbot_api_star.Star = FakeStar
    astrbot_api_star.StarTools = FakeStarTools

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api
    sys.modules["astrbot.api.all"] = astrbot_api_all
    sys.modules["astrbot.api.event"] = astrbot_api_event
    sys.modules["astrbot.api.event.filter"] = astrbot_api_event_filter
    sys.modules["astrbot.api.message_components"] = astrbot_api_message_components
    sys.modules["astrbot.api.star"] = astrbot_api_star


class FakeImageComponent:
    def __init__(self, file: str):
        self.file = file

    @staticmethod
    def fromBytes(data: bytes) -> "FakeImageComponent":
        return FakeImageComponent(f"bytes:{data[:12]!r}")

    @staticmethod
    def fromBase64(data: str) -> "FakeImageComponent":
        return FakeImageComponent(f"base64:{data[:12]}")


class FakeEvent:
    def __init__(self, failures: int):
        self.failures = failures
        self.sent: list[object] = []

    def chain_result(self, chain: list[object]):
        return types.SimpleNamespace(chain=chain)

    def plain_result(self, text: str):
        return types.SimpleNamespace(chain=[text])

    async def send(self, result):
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("simulated rich media failure")
        self.sent.append(result)


async def _run_flow_smoke() -> None:
    _install_astrbot_stubs()
    import astrbot_plugin_phi_plugin.main as plugin_main

    original_image = plugin_main.Comp.Image
    plugin_main.Comp.Image = FakeImageComponent
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "source.png"
            Image.new("RGB", (80, 60), (30, 120, 210)).save(image_path, format="PNG")

            event = FakeEvent(failures=2)
            plugin = object.__new__(plugin_main.AstrBotPhiPlugin)
            plugin.plugin_config = types.SimpleNamespace(quote_reply=False)
            await plugin._send_image_with_fallback(event, image_path)

        if event.failures != 0:
            raise SystemExit("fallback flow did not consume expected failures")
        if len(event.sent) != 1:
            raise SystemExit(f"expected exactly one successful send, got {len(event.sent)}")
    finally:
        plugin_main.Comp.Image = original_image


def main() -> None:
    asyncio.run(_run_flow_smoke())
    print("image send fallback flow smoke passed")


if __name__ == "__main__":
    main()
