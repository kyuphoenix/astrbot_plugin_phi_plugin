from __future__ import annotations

import random
from pathlib import Path

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.all import AstrBotConfig, logger
from astrbot.api.star import Context, Star, StarTools

from .phi_core.config import PluginConfig
from .phi_core.data import SongCatalog, SongSearcher, load_catalog
from .phi_core.paths import PluginPaths
from .phi_core.query import compute_b30, find_song_scores, summarize_user
from .phi_core.render import text as render
from .phi_core.save import (
    PhiApiClient,
    SaveNotAvailable,
    SaveStore,
    StoreError,
    normalize_save,
    snapshot_to_json,
)


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
        logger.info(f"astrbot_plugin_phi_plugin loaded {len(self.catalog)} songs")

    @filter.command("phi", alias={"pgr", "屁股肉"})
    async def phi(self, event: AstrMessageEvent):
        """Phigros 查询核心命令。"""
        event.stop_event()
        command, args = self._parse_native_command(event.get_message_str())
        async for result in self._dispatch(event, command, args):
            yield result

    @staticmethod
    def _parse_native_command(message: str) -> tuple[str, str]:
        text = (message or "").strip()
        if not text:
            return "help", ""

        # AstrBot has already matched the command. Its message string still
        # includes the command token, as shown in the plugin guide examples.
        parts = text.split(maxsplit=1)
        rest = parts[1].strip() if len(parts) > 1 else "help"
        sub_parts = rest.split(maxsplit=1)
        command = sub_parts[0].casefold() if sub_parts else "help"
        args = sub_parts[1].strip() if len(sub_parts) > 1 else ""
        return command, args

    async def _dispatch(self, event: AstrMessageEvent, command: str, args: str):
        if command in {"help", "帮助", "菜单", "命令", "指令"}:
            yield event.plain_result(render.render_help())
            return
        if command in {"song", "曲"}:
            yield event.plain_result(self._cmd_song(args))
            return
        if command in {"search", "查找", "检索"}:
            yield event.plain_result(self._cmd_search(args))
            return
        if command in {"rand", "random", "随机"}:
            yield event.plain_result(render.render_random(random.choice(self.catalog.all_songs())))
            return
        if command in {"ill", "曲绘"}:
            async for result in self._cmd_ill(event, args):
                yield result
            return
        if command in {"bind", "绑定", "cnbind", "gbbind"}:
            yield event.plain_result(self._cmd_bind(event, args))
            return
        if command in {"unbind", "解绑"}:
            yield event.plain_result(render.render_unbind(self.store.unbind(event.get_sender_id())))
            return
        if command == "clean":
            yield event.plain_result(render.render_unbind(self.store.clean(event.get_sender_id())))
            return
        if command in {"update", "更新存档"}:
            yield event.plain_result(await self._cmd_update(event))
            return
        if command in {"b30", "rks", "pgr"}:
            yield event.plain_result(self._cmd_b30(event))
            return
        if command in {"score", "单曲成绩"}:
            yield event.plain_result(self._cmd_score(event, args))
            return
        if command in {"info", "data"}:
            yield event.plain_result(self._cmd_info(event))
            return
        yield event.plain_result(render.render_unsupported(f"phi {command}"))

    def _cmd_song(self, args: str) -> str:
        if not args:
            return render.render_need_query("song")
        song = self.searcher.best(args)
        if not song:
            return render.render_search(args, [])
        return render.render_song(song)

    def _cmd_search(self, args: str) -> str:
        if not args:
            return render.render_need_query("search")
        return render.render_search(args, self.searcher.search(args, limit=10))

    async def _cmd_ill(self, event: AstrMessageEvent, args: str):
        if not args:
            yield event.plain_result(render.render_need_query("ill"))
            return
        song = self.searcher.best(args)
        if not song:
            yield event.plain_result(render.render_search(args, []))
            return
        path = self._find_illustration(song)
        if path:
            yield event.image_result(str(path))
            return
        yield event.plain_result(render.render_missing_illustration(song))

    def _cmd_bind(self, event: AstrMessageEvent, args: str) -> str:
        token = args.strip().split()[0] if args.strip() else ""
        try:
            self.store.bind(event.get_sender_id(), token)
        except StoreError as exc:
            return str(exc)
        return render.render_bind_ok()

    async def _cmd_update(self, event: AstrMessageEvent) -> str:
        user_id = event.get_sender_id()
        token = self.store.get_token(user_id)
        if not token:
            return render.render_not_bound()
        try:
            raw = await self.client.fetch_cloud_save(token, user_id=user_id)
            snapshot = normalize_save(user_id, token, raw)
            self.store.save_snapshot(user_id, snapshot_to_json(snapshot))
            return render.render_update_ok(summarize_user(snapshot, self.catalog))
        except SaveNotAvailable as exc:
            return render.render_update_failed(str(exc))
        except Exception as exc:
            logger.warning("phi update failed", exc_info=True)
            return render.render_update_failed(str(exc))

    def _cmd_b30(self, event: AstrMessageEvent) -> str:
        snapshot = self._load_snapshot(event)
        if not snapshot:
            return render.render_no_cached_save()
        result = compute_b30(snapshot, self.catalog, limit=self.plugin_config.max_b30)
        return render.render_b30(result, limit=self.plugin_config.max_b30)

    def _cmd_score(self, event: AstrMessageEvent, args: str) -> str:
        if not args:
            return render.render_need_query("score")
        snapshot = self._load_snapshot(event)
        if not snapshot:
            return render.render_no_cached_save()
        song = self.searcher.best(args)
        if not song:
            return render.render_search(args, [])
        return render.render_score(song, find_song_scores(snapshot, self.catalog, song))

    def _cmd_info(self, event: AstrMessageEvent) -> str:
        snapshot = self._load_snapshot(event)
        if not snapshot:
            return render.render_no_cached_save()
        return render.render_user_info(summarize_user(snapshot, self.catalog))

    def _load_snapshot(self, event: AstrMessageEvent):
        raw = self.store.load_snapshot(event.get_sender_id())
        if not raw:
            return None
        token = self.store.get_token(event.get_sender_id()) or str(raw.get("session") or "")
        try:
            return normalize_save(event.get_sender_id(), token, raw)
        except SaveNotAvailable:
            return None

    def _find_illustration(self, song) -> Path | None:
        candidates: list[Path] = []
        base_id = song.id.removesuffix(".0")
        for folder in [
            self.paths.downloaded_original_ill,
            self.paths.downloaded_original_ill / "ill",
            self.paths.downloaded_original_ill / "SP",
            self.paths.original_ill,
            self.paths.original_ill / "ill",
            self.paths.original_ill / "SP",
        ]:
            candidates.append(folder / f"{base_id}.png")
        if song.illustration:
            candidates.append(self.paths.other_ill / song.illustration)
        if song.illustration_big:
            candidates.append(self.paths.other_ill / song.illustration_big)
        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return None
