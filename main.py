from __future__ import annotations

from pathlib import Path

from astrbot.api.all import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .phi_core.commands import CommandContext, CommandResult, dispatch
from .phi_core.config import PluginConfig
from .phi_core.data import SongCatalog, SongSearcher, load_catalog
from .phi_core.paths import PluginPaths
from .phi_core.render import image as image_render
from .phi_core.save import PhiApiClient, SaveStore


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
        self.command_context = CommandContext(
            config=self.plugin_config,
            paths=self.paths,
            catalog=self.catalog,
            searcher=self.searcher,
            store=self.store,
            client=self.client,
        )
        logger.info(f"astrbot_plugin_phi_plugin loaded {len(self.catalog)} songs")

    @filter.command("phi", alias={"pgr", "屁股肉"})
    async def phi(self, event: AstrMessageEvent):
        """Phigros 查询核心命令。"""
        event.stop_event()
        command, args = self._parse_native_command(event.get_message_str())
        result = await dispatch(self.command_context, event.get_sender_id(), command, args)
        yield self._to_astrbot_result(event, result)

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

    def _to_astrbot_result(self, event: AstrMessageEvent, result: CommandResult):
        if result.kind == "image":
            return event.image_result(result.value)
        if self.plugin_config.render_mode == "image":
            try:
                path = image_render.render_text_panel(self.paths, result.value)
                return event.image_result(str(path))
            except Exception as exc:
                logger.warning(f"phi image render failed, fallback to text: {exc}")
        return event.plain_result(result.value)
