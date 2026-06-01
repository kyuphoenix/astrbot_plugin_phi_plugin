from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api.all import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .phi_core.commands import CommandContext, CommandResult, dispatch
from .phi_core.config import PluginConfig
from .phi_core.data import SongCatalog, SongSearcher, apply_aliases, load_catalog
from .phi_core.paths import PluginPaths
from .phi_core.render import image as image_render
from .phi_core.render.send_variants import build_image_send_variant
from .phi_core.data.ill_download import ensure_resources_blocking
from .phi_core.save import PhiApiClient, SaveStore, TapTapQrLogin

_B_ALIASES = {f"b{index}" for index in range(1, 101)} - {"b30"}
_P_ALIASES = {f"p{index}" for index in range(1, 101)} - {"p30"}
_X_ALIASES = {f"x{index}" for index in range(1, 101)} - {"x30"}
_FC_ALIASES = {f"fc{index}" for index in range(1, 101)} - {"fc30"}
_ARCGROS_ALIASES = {f"arcgrosb{index}" for index in range(1, 101)}


class AstrBotPhiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.plugin_config = PluginConfig.from_astrbot(config)
        root = Path(__file__).resolve().parent
        data_dir = Path(StarTools.get_data_dir("astrbot_plugin_phi_plugin"))
        self.paths = PluginPaths.from_root(root, data_dir=data_dir)
        self.paths.illustration_source = self.plugin_config.illustration_source
        self.paths.illustration_url_proxy = self.plugin_config.illustration_url_proxy
        self.paths.ensure_data_dir()
        resource_result = ensure_resources_blocking(self.plugin_config, self.paths)
        self.catalog: SongCatalog = load_catalog(self.paths.info)
        self.store = SaveStore(self.paths.data_dir)
        apply_aliases(self.catalog, self.store.load_custom_aliases())
        self.searcher = SongSearcher(self.catalog)
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
            f"illustration_source={self.plugin_config.illustration_source}; "
            f"illustration_url_proxy={'set' if self.plugin_config.illustration_url_proxy else 'empty'}; "
            f"data_dir={self.paths.data_dir}; font={font_path}; font_exists={Path(font_path).exists()}"
        )
        if resource_result is not None:
            logger.info(
                "astrbot_plugin_phi_plugin downloaded upstream resources "
                f"to {resource_result.target}; commit={resource_result.commit}"
            )

    @filter.command_group("phi")
    def phi(self):
        """Phigros command group."""
        pass

    @filter.command("pgr", alias={"\u5c41\u80a1\u8089"})
    async def pgr_shortcut(self, event: AstrMessageEvent):
        """Phigros B30/RKS shortcut."""
        yield await self._dispatch_phi_command(event, "pgr", grouped=False)

    @phi.command('achievement', alias={'ahv'})
    async def phi_achievement(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'achievement')

    @phi.command('addtag', alias={'retag', 'subtag'})
    async def phi_addtag(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'addtag')

    @phi.command('alias')
    async def phi_alias(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'alias')

    @phi.command('api')
    async def phi_api(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'api')

    @phi.command('ans', alias={'\u7b54\u6848', '\u7ed3\u675f'})
    async def phi_ans(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'ans')

    @phi.command('arcgros', alias=_ARCGROS_ALIASES)
    async def phi_arcgros(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'arcgros')

    @phi.command('auth', alias={'login', '\u767b\u5f55'})
    async def phi_auth(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'auth')

    @phi.command('b30', alias=_B_ALIASES)
    async def phi_b30(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'b30')

    @phi.command('best')
    async def phi_best(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'best')

    @phi.command('bind', alias={'\u7ed1\u5b9a'})
    async def phi_bind(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'bind')

    @phi.command('chap')
    async def phi_chap(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'chap')

    @phi.command('chart')
    async def phi_chart(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'chart')

    @phi.command('clean')
    async def phi_clean(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'clean')

    @phi.command('cnbind', alias={'cn\u7ed1\u5b9a'})
    async def phi_cnbind(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'cnbind')

    @phi.command('com', alias={'\u8ba1\u7b97'})
    async def phi_com(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'com')

    @phi.command('comment', alias={'cmt', '\u8bc4\u4ef7', '\u8bc4\u8bba'})
    async def phi_comment(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'comment')

    @phi.command('data')
    async def phi_data(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'data')

    @phi.command('delnick', alias={'delnic', '\u5220\u9664\u522b\u540d'})
    async def phi_delnick(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'delnick')

    @phi.command('down', alias={'downill', 'download', 'illupdate', '\u4e0b\u8f7d', '\u4e0b\u8f7d\u66f2\u7ed8', '\u66f4\u65b0\u66f2\u7ed8'})
    async def phi_down(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'down')

    @phi.command('fc30', alias=_FC_ALIASES)
    async def phi_fc30(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'fc30')

    @phi.command('gbbind', alias={'gb\u7ed1\u5b9a'})
    async def phi_gbbind(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'gbbind')

    @phi.command('guess', alias={'\u731c\u66f2\u7ed8'})
    async def phi_guess(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'guess')

    @phi.command('help', alias={'\u547d\u4ee4', '\u5e2e\u52a9', '\u6307\u4ee4', '\u83dc\u5355'})
    async def phi_help(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'help')

    @phi.command('hisb30')
    async def phi_hisb30(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'hisb30')

    @phi.command('2025history', alias={'\u5e74\u5ea6\u603b\u7ed3'})
    async def phi_history2025(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, '2025history')

    @phi.command('id', alias={'apiid', 'uid', '\u67e5\u8be2id'})
    async def phi_id(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'id')

    @phi.command('ill', alias={'\u66f2\u7ed8'})
    async def phi_ill(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'ill')

    @phi.command('info')
    async def phi_info(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'info')

    @phi.command('info1')
    async def phi_info1(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'info1')

    @phi.command('info2')
    async def phi_info2(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'info2')

    @phi.command('jrrp', alias={'\u4eca\u65e5\u4eba\u54c1'})
    async def phi_jrrp(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'jrrp')

    @phi.command('list')
    async def phi_list(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'list')

    @phi.command('live')
    async def phi_live(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'live')

    @phi.command('lmtacc')
    async def phi_lmtacc(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'lmtacc')

    @phi.command('ltr', alias={'letter', '\u5f00\u5b57\u6bcd'})
    async def phi_ltr(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'ltr')

    @phi.command('lvscore', alias={'lvsco', 'scolv'})
    async def phi_lvscore(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'lvscore')

    @phi.command('mycmt')
    async def phi_mycmt(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'mycmt')

    @phi.command('myset', alias={'mysetting', '\u7528\u6237\u8bbe\u7f6e', '\u4e2a\u4eba\u8bbe\u7f6e'})
    async def phi_myset(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'myset')

    @phi.command('newlog')
    async def phi_newlog(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'newlog')

    @phi.command('newnotice')
    async def phi_newnotice(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'newnotice')

    @phi.command('open', alias={'\u63ed\u5f00', '\u6253\u5f00', '\u7ffb\u5f00', '\u5f00'})
    async def phi_open(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'open')

    @phi.command('p30', alias=_P_ALIASES)
    async def phi_p30(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'p30')

    @phi.command('pgr', alias={'\u5c41\u80a1\u8089'})
    async def phi_pgr(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'pgr')

    @phi.command('rand', alias={'random', '\u968f\u673a'})
    async def phi_rand(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'rand')

    @phi.command('randclg')
    async def phi_randclg(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'randclg')

    @phi.command('rankfind', alias={'\u67e5\u8be2\u6392\u540d'})
    async def phi_rankfind(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'rankfind')

    @phi.command('ranklist', alias={'\u6392\u884c\u699c'})
    async def phi_ranklist(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'ranklist')

    @phi.command('recmt')
    async def phi_recmt(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'recmt')

    @phi.command('renderdiag', alias={'\u6e32\u67d3\u8bca\u65ad'})
    async def phi_renderdiag(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'renderdiag')

    @phi.command('rks')
    async def phi_rks(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'rks')

    @phi.command('retask', alias={'\u5237\u65b0\u4efb\u52a1'})
    async def phi_retask(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'retask')

    @phi.command('score', alias={'\u5355\u66f2\u6210\u7ee9'})
    async def phi_score(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'score')

    @phi.command('search', alias={'\u67e5\u627e', '\u68c0\u7d22'})
    async def phi_search(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'search')

    @phi.command('sessiontoken', alias={'tk', 'token'})
    async def phi_sessiontoken(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'sessiontoken')

    @phi.command('send', alias={'\u9001', '\u8f6c'})
    async def phi_send(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'send')

    @phi.command('setapitoken')
    async def phi_setapitoken(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'setapitoken')

    @phi.command('setnick', alias={'setnic', '\u8bbe\u7f6e\u522b\u540d'})
    async def phi_setnick(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'setnick')

    @phi.command('settag')
    async def phi_settag(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'settag')

    @phi.command('song', alias={'\u66f2'})
    async def phi_song(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'song')

    @phi.command('sign', alias={'signin', '\u7b7e\u5230', '\u6253\u5361'})
    async def phi_sign(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'sign')

    @phi.command('suggest', alias={'\u63a8\u5206', '\u63a8\u5206\u5efa\u8bae'})
    async def phi_suggest(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'suggest')

    @phi.command('table', alias={'\u5b9a\u6570\u8868'})
    async def phi_table(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'table')

    @phi.command('tag')
    async def phi_tag(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'tag')

    @phi.command('task', alias={'tasks', '\u6211\u7684\u4efb\u52a1'})
    async def phi_task(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'task')

    @phi.command('tips')
    async def phi_tips(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'tips')

    @phi.command('tokenlist', alias={'tkls', 'lstk'})
    async def phi_tokenlist(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'tokenlist')

    @phi.command('tip', alias={'\u63d0\u793a'})
    async def phi_tip(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'tip')

    @phi.command('tipgame', alias={'\u63d0\u793a\u731c\u66f2'})
    async def phi_tipgame(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'tipgame')

    @phi.command('theme')
    async def phi_theme(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'theme')

    @phi.command('unbind', alias={'\u89e3\u7ed1'})
    async def phi_unbind(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'unbind')

    @phi.command('update', alias={'\u66f4\u65b0\u5b58\u6863'})
    async def phi_update(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, 'update')

    @phi.command('x30', alias=_X_ALIASES)
    async def phi_x30(self, event: AstrMessageEvent):
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'x30')

    async def _dispatch_phi_command(self, event: AstrMessageEvent, command: str, *, grouped: bool = True):
        event.stop_event()
        args = self._extract_command_args(event.get_message_str(), grouped=grouped)

        async def send_intermediate(result: CommandResult) -> None:
            if result.kind == "image":
                await self._send_image_with_fallback(event, result.value)
                return
            await event.send(event.plain_result(result.value))

        command_context = self._command_context_for_event(event, sender=send_intermediate)
        result = await dispatch(command_context, event.get_sender_id(), command, args)
        return await self._send_command_result(event, result)

    def _command_context_for_event(
        self,
        event: AstrMessageEvent,
        *,
        sender: Callable[[CommandResult], Awaitable[None]] | None = None,
    ) -> CommandContext:
        return CommandContext(
            config=self.command_context.config,
            paths=self.command_context.paths,
            catalog=self.command_context.catalog,
            searcher=self.command_context.searcher,
            store=self.command_context.store,
            client=self.command_context.client,
            taptap=self.command_context.taptap,
            html_render=self.html_render,
            sender=sender,
            is_admin=bool(event.is_admin()),
            session_id=self._event_session_id(event),
        )

    @staticmethod
    def _event_session_id(event: AstrMessageEvent) -> str:
        for getter in ("get_session_id", "get_group_id", "get_sender_id"):
            try:
                value = getattr(event, getter)()
            except Exception:
                value = ""
            if value:
                return str(value)
        return ""

    @staticmethod
    def _extract_command_args(message: str, *, grouped: bool) -> str:
        text = (message or "").strip()
        if not text:
            return ""
        parts = text.split(maxsplit=2 if grouped else 1)
        if grouped:
            return parts[2].strip() if len(parts) > 2 else ""
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def _extract_group_command(message: str) -> str:
        parts = (message or "").strip().split(maxsplit=2)
        return parts[1].strip() if len(parts) > 1 else ""

    async def _send_command_result(
        self,
        event: AstrMessageEvent,
        result: CommandResult,
    ):
        if result.kind == "image":
            await self._send_image_with_fallback(event, result.value)
            return None
        return event.plain_result(result.value)

    @staticmethod
    def _image_component(path: str | Path):
        return AstrBotPhiPlugin._image_component_from_bytes(Path(path).read_bytes())

    @staticmethod
    def _image_component_from_bytes(image_bytes: bytes):
        if hasattr(Comp.Image, "fromBytes"):
            return Comp.Image.fromBytes(image_bytes)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return Comp.Image.fromBase64(encoded)

    async def _send_image_with_fallback(self, event: AstrMessageEvent, path: str | Path) -> None:
        last_error: Exception | None = None
        for variant_name in ("original", "jpg", "webp"):
            try:
                variant = build_image_send_variant(path, variant_name)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "phi image fallback conversion failed "
                    f"format={variant_name}; path={path}; error={exc}",
                    exc_info=True,
                )
                continue

            try:
                await event.send(event.chain_result([self._image_component_from_bytes(variant.data)]))
                if variant.name != "original":
                    logger.info(
                        "phi image sent with fallback "
                        f"format={variant.name}; bytes={len(variant.data)}; path={path}"
                    )
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "phi image send failed "
                    f"format={variant.name}; bytes={len(variant.data)}; path={path}; error={exc}",
                    exc_info=True,
                )

        message = "图片发送失败：原图、JPG 压缩图、WebP 压缩图都发送失败，请稍后重试。"
        if last_error is not None:
            message += f"\n最后一次错误：{last_error}"
        await event.send(event.plain_result(message))
