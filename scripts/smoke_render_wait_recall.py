from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = ROOT.parent
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))


def _decorator(*_args: Any, **_kwargs: Any):
    def wrap(func: Any) -> Any:
        return func

    return wrap


def _command_group(*_args: Any, **_kwargs: Any):
    def wrap(func: Any) -> Any:
        func.command = _decorator
        return func

    return wrap


def _install_astrbot_stubs() -> None:
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    components = types.ModuleType("astrbot.api.message_components")
    all_module = types.ModuleType("astrbot.api.all")
    event_module = types.ModuleType("astrbot.api.event")
    filter_module = types.ModuleType("astrbot.api.event.filter")
    star_module = types.ModuleType("astrbot.api.star")

    class Reply:
        def __init__(self, id: Any):
            self.id = id

    class Plain:
        def __init__(self, text: str):
            self.text = text

    class Image:
        @classmethod
        def fromBytes(cls, data: bytes):
            return data

        @classmethod
        def fromBase64(cls, data: str):
            return data

    class Logger:
        def debug(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def info(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def warning(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    class Star:
        pass

    class StarTools:
        @staticmethod
        def get_data_dir(_name: str) -> str:
            return str(ROOT / ".tmp_smoke_data")

    class CustomFilter:
        pass

    components.Reply = Reply
    components.Plain = Plain
    components.Image = Image
    all_module.AstrBotConfig = dict
    all_module.logger = Logger()
    event_module.AstrMessageEvent = object
    event_module.filter = filter_module
    filter_module.CustomFilter = CustomFilter
    filter_module.command_group = _command_group
    filter_module.command = _decorator
    filter_module.event_message_type = _decorator
    filter_module.custom_filter = _decorator
    filter_module.EventMessageType = types.SimpleNamespace(ALL="ALL")
    star_module.Context = object
    star_module.Star = Star
    star_module.StarTools = StarTools

    sys.modules.setdefault("astrbot", astrbot)
    sys.modules.setdefault("astrbot.api", api)
    sys.modules["astrbot.api.message_components"] = components
    sys.modules["astrbot.api.all"] = all_module
    sys.modules["astrbot.api.event"] = event_module
    sys.modules["astrbot.api.event.filter"] = filter_module
    sys.modules["astrbot.api.star"] = star_module


class FakeConfig:
    send_render_wait_message = True
    render_wait_message = "正在渲染图片，请稍后"
    render_mode = "image"
    quote_reply = True


class FakeMessageObj:
    message_id = 987654


class FakeEvent:
    message_obj = FakeMessageObj()

    def __init__(self, bot: Any):
        self.bot = bot
        self.fallback_sends = 0

    def get_group_id(self) -> str:
        return "10001"

    def get_sender_id(self) -> str:
        return "20002"

    async def send(self, _result: Any) -> None:
        self.fallback_sends += 1
        return None

    def plain_result(self, text: str) -> str:
        return text

    def chain_result(self, chain: list[Any]) -> list[Any]:
        return chain


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.deleted: list[Any] = []

    async def send_group_msg(self, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(kwargs)
        return {"message_id": 123456}

    async def delete_msg(self, **kwargs: Any) -> None:
        self.deleted.append(kwargs["message_id"])


async def main() -> None:
    _install_astrbot_stubs()
    plugin_module = importlib.import_module(f"{ROOT.name}.main")
    plugin = plugin_module.AstrBotPhiPlugin.__new__(plugin_module.AstrBotPhiPlugin)
    plugin.plugin_config = FakeConfig()
    plugin.html_render = object()

    bot = FakeBot()
    event = FakeEvent(bot)
    message_id = await plugin._send_render_wait_message(event, "pgr")
    if message_id != 123456:
        raise SystemExit(f"wait message_id mismatch: {message_id!r}")
    if event.fallback_sends:
        raise SystemExit("direct OneBot send should not fall back to event.send")
    if len(bot.sent) != 1:
        raise SystemExit(f"expected one direct send, got {bot.sent!r}")
    sent = bot.sent[0]
    if sent.get("group_id") != 10001:
        raise SystemExit(f"group_id should be converted to int, got {sent!r}")
    message = sent.get("message")
    if [item["type"] for item in message] != ["reply", "text"]:
        raise SystemExit(f"unexpected OneBot message segments: {message!r}")
    if message[0]["data"]["id"] != "987654":
        raise SystemExit(f"reply id mismatch: {message!r}")

    await plugin._recall_message(event, message_id)
    if bot.deleted != [123456]:
        raise SystemExit(f"delete_msg was not called correctly: {bot.deleted!r}")

    print("render wait recall smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
