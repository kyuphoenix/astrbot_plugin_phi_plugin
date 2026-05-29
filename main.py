from __future__ import annotations

import base64
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api.all import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .phi_core.commands import CommandContext, CommandResult, dispatch
from .phi_core.config import PluginConfig
from .phi_core.data import SongCatalog, SongSearcher, load_catalog
from .phi_core.paths import PluginPaths
from .phi_core.render import image as image_render
from .phi_core.render import panel as panel_render
from .phi_core.save import PhiApiClient, SaveStore, TapTapQrLogin


class AstrBotPhiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.plugin_config = PluginConfig.from_astrbot(config)
        root = Path(__file__).resolve().parent
        data_dir = Path(StarTools.get_data_dir("astrbot_plugin_phi_plugin"))
        self.paths = PluginPaths.from_root(root, data_dir=data_dir)
        self.paths.ensure_data_dir()
        self.catalog: SongCatalog = load_catalog(self.paths.info)
        self.searcher = SongSearcher(self.catalog)
        self.store = SaveStore(self.paths.data_dir)
        self.client = PhiApiClient(self.plugin_config)
        self.taptap = TapTapQrLogin(self.plugin_config, self.paths)
        self.command_context = CommandContext(
            config=self.plugin_config,
            paths=self.paths,
            catalog=self.catalog,
            searcher=self.searcher,
            store=self.store,
            client=self.client,
            taptap=self.taptap,
        )
        font_path = image_render.selected_font_path(self.paths)
        logger.info(
            "astrbot_plugin_phi_plugin loaded "
            f"{len(self.catalog)} songs; render_mode={self.plugin_config.render_mode}; "
            f"render_backend={self.plugin_config.render_backend}; "
            f"data_dir={self.paths.data_dir}; font={font_path}; font_exists={Path(font_path).exists()}"
        )

    @filter.command("phi", alias={"pgr", "屁股肉"})
    async def phi(self, event: AstrMessageEvent):
        """Phigros 查询核心命令。"""
        event.stop_event()
        command, args = self._parse_native_command(event.get_message_str())
        async def send_intermediate(result: CommandResult) -> None:
            await event.send(await self._to_astrbot_result(event, result))

        command_context = CommandContext(
            config=self.command_context.config,
            paths=self.command_context.paths,
            catalog=self.command_context.catalog,
            searcher=self.command_context.searcher,
            store=self.command_context.store,
            client=self.command_context.client,
            taptap=self.command_context.taptap,
            html_render=self.html_render,
            sender=send_intermediate,
        )
        result = await dispatch(command_context, event.get_sender_id(), command, args)
        yield await self._to_astrbot_result(event, result)

    @staticmethod
    def _parse_native_command(message: str) -> tuple[str, str]:
        text = (message or "").strip()
        if not text:
            return "help", ""

        # AstrBot has already matched the command. Its message string still
        # includes the command token, as shown in the plugin guide examples.
        parts = text.split(maxsplit=1)
        root = parts[0].casefold()
        if root in {"pgr", "屁股肉"}:
            return root, parts[1].strip() if len(parts) > 1 else ""
        rest = parts[1].strip() if len(parts) > 1 else "help"
        sub_parts = rest.split(maxsplit=1)
        command = sub_parts[0].casefold() if sub_parts else "help"
        args = sub_parts[1].strip() if len(sub_parts) > 1 else ""
        return command, args

    async def _to_astrbot_result(self, event: AstrMessageEvent, result: CommandResult):
        if result.kind == "image":
            return event.chain_result([self._image_component(result.value)])
        if self.plugin_config.render_mode == "image":
            try:
                path = await panel_render.render_text_panel(
                    self.plugin_config,
                    self.paths,
                    result.value,
                    html_render=self.html_render,
                )
                return event.chain_result([self._image_component(path)])
            except Exception as exc:
                logger.warning(
                    "phi image render failed, fallback to text: "
                    f"{exc}; render_mode={self.plugin_config.render_mode}; "
                    f"render_backend={self.plugin_config.render_backend}; "
                    f"resources={self.paths.resources}; fonts={image_render.font_diagnostics(self.paths)}"
                )
        return event.plain_result(result.value)

    @staticmethod
    def _image_component(path: str | Path):
        image_bytes = Path(path).read_bytes()
        if hasattr(Comp.Image, "fromBytes"):
            return Comp.Image.fromBytes(image_bytes)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return Comp.Image.fromBase64(encoded)
