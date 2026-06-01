from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api.all import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import CustomFilter
from astrbot.api.star import Context, Star, StarTools

from .phi_core.commands import CommandContext, CommandResult, dispatch
from .phi_core.commands._games import handle_game_reply, has_active_game_session
from .phi_core.concurrency import AsyncKeyedLock
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
_GAME_STATE_COMMANDS = {"guess", "tipgame", "ltr", "tip", "ans", "open"}


class ActivePhiGameFilter(CustomFilter):
    enabled = False

    def filter(self, event: AstrMessageEvent, cfg: Any) -> bool:
        del cfg
        if not self.enabled:
            return False
        message = (event.get_message_str() or "").strip()
        if not message or message.casefold().startswith("phi "):
            return False
        session_id = AstrBotPhiPlugin._event_session_id(event)
        return has_active_game_session(session_id, event.get_sender_id())


class AstrBotPhiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.plugin_config = PluginConfig.from_astrbot(config)
        ActivePhiGameFilter.enabled = self.plugin_config.game_reply_listener
        self._user_command_locks = AsyncKeyedLock()
        self._game_session_locks = AsyncKeyedLock()
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

    @filter.command_group("phi", desc="Phigros 指令组，包含查分、曲库、小游戏、资源管理等子命令。")
    def phi(self):
        """Phigros 指令组，包含查分、曲库、小游戏、资源管理等子命令。"""
        pass

    @filter.command("pgr", alias={"\u5c41\u80a1\u8089"}, desc="快速查看当前绑定玩家的 B30/RKS 成绩面板。")
    async def pgr_shortcut(self, event: AstrMessageEvent):
        """快速查看当前绑定玩家的 B30/RKS 成绩面板。"""
        yield await self._dispatch_phi_command(event, "pgr", grouped=False)

    @phi.command('achievement', alias={'ahv'}, desc="查看玩家成就统计与完成情况。")
    async def phi_achievement(self, event: AstrMessageEvent):
        """查看玩家成就统计与完成情况。"""
        yield await self._dispatch_phi_command(event, 'achievement')

    @phi.command('addtag', alias={'retag', 'subtag'}, desc="为谱面添加或提交标签。")
    async def phi_addtag(self, event: AstrMessageEvent):
        """为谱面添加或提交标签。"""
        yield await self._dispatch_phi_command(event, 'addtag')

    @phi.command('alias', desc="查询、添加或管理曲目别名。")
    async def phi_alias(self, event: AstrMessageEvent):
        """查询、添加或管理曲目别名。"""
        yield await self._dispatch_phi_command(event, 'alias')

    @phi.command('api', desc="查看 Phi 查分平台 API 相关帮助。")
    async def phi_api(self, event: AstrMessageEvent):
        """查看 Phi 查分平台 API 相关帮助。"""
        yield await self._dispatch_phi_command(event, 'api')

    @phi.command('ans', alias={'\u7b54\u6848', '\u7ed3\u675f'}, desc="公布当前小游戏答案并结束游戏。")
    async def phi_ans(self, event: AstrMessageEvent):
        """公布当前小游戏答案并结束游戏。"""
        yield await self._dispatch_phi_command(event, 'ans')

    @phi.command('arcgros', alias=_ARCGROS_ALIASES, desc="以 Arcgros 风格查看 B19/B30 等成绩面板。")
    async def phi_arcgros(self, event: AstrMessageEvent):
        """以 Arcgros 风格查看 B19/B30 等成绩面板。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'arcgros')

    @phi.command('auth', alias={'login', '\u767b\u5f55'}, desc="使用查分平台 API Token 登录并绑定账号。")
    async def phi_auth(self, event: AstrMessageEvent):
        """使用查分平台 API Token 登录并绑定账号。"""
        yield await self._dispatch_phi_command(event, 'auth')

    @phi.command('b30', alias=_B_ALIASES, desc="查看 Best 30/Best N 成绩与 RKS 面板。")
    async def phi_b30(self, event: AstrMessageEvent):
        """查看 Best 30/Best N 成绩与 RKS 面板。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'b30')

    @phi.command('best', desc="生成文字版 B30 成绩列表。")
    async def phi_best(self, event: AstrMessageEvent):
        """生成文字版 B30 成绩列表。"""
        yield await self._dispatch_phi_command(event, 'best')

    @phi.command('bind', alias={'\u7ed1\u5b9a'}, desc="绑定 sessionToken、查询 ID 或 TapTap 二维码登录。")
    async def phi_bind(self, event: AstrMessageEvent):
        """绑定 sessionToken、查询 ID 或 TapTap 二维码登录。"""
        yield await self._dispatch_phi_command(event, 'bind')

    @phi.command('chap', desc="按章节查询曲目列表。")
    async def phi_chap(self, event: AstrMessageEvent):
        """按章节查询曲目列表。"""
        yield await self._dispatch_phi_command(event, 'chap')

    @phi.command('chart', desc="查询指定曲目的谱面信息与标签。")
    async def phi_chart(self, event: AstrMessageEvent):
        """查询指定曲目的谱面信息与标签。"""
        yield await self._dispatch_phi_command(event, 'chart')

    @phi.command('clean', desc="清理当前用户的绑定与本地缓存数据。")
    async def phi_clean(self, event: AstrMessageEvent):
        """清理当前用户的绑定与本地缓存数据。"""
        yield await self._dispatch_phi_command(event, 'clean')

    @phi.command('cnbind', alias={'cn\u7ed1\u5b9a'}, desc="按国服方式绑定账号或查询 ID。")
    async def phi_cnbind(self, event: AstrMessageEvent):
        """按国服方式绑定账号或查询 ID。"""
        yield await self._dispatch_phi_command(event, 'cnbind')

    @phi.command('com', alias={'\u8ba1\u7b97'}, desc="根据分数、准确率和定数计算单曲 RKS。")
    async def phi_com(self, event: AstrMessageEvent):
        """根据分数、准确率和定数计算单曲 RKS。"""
        yield await self._dispatch_phi_command(event, 'com')

    @phi.command('comment', alias={'cmt', '\u8bc4\u4ef7', '\u8bc4\u8bba'}, desc="查看或发布曲目在线评论。")
    async def phi_comment(self, event: AstrMessageEvent):
        """查看或发布曲目在线评论。"""
        yield await self._dispatch_phi_command(event, 'comment')

    @phi.command('data', desc="查看当前存档的 Data 数量与进度信息。")
    async def phi_data(self, event: AstrMessageEvent):
        """查看当前存档的 Data 数量与进度信息。"""
        yield await self._dispatch_phi_command(event, 'data')

    @phi.command('delnick', alias={'delnic', '\u5220\u9664\u522b\u540d'}, desc="删除已设置的曲目别名。")
    async def phi_delnick(self, event: AstrMessageEvent):
        """删除已设置的曲目别名。"""
        yield await self._dispatch_phi_command(event, 'delnick')

    @phi.command('down', alias={'downill', 'download', 'illupdate', '\u4e0b\u8f7d', '\u4e0b\u8f7d\u66f2\u7ed8', '\u66f4\u65b0\u66f2\u7ed8'}, desc="下载或更新插件资源、曲绘资源。")
    async def phi_down(self, event: AstrMessageEvent):
        """下载或更新插件资源、曲绘资源。"""
        yield await self._dispatch_phi_command(event, 'down')

    @phi.command('fc30', alias=_FC_ALIASES, desc="查看 Full Combo 模式下的 Top N 成绩。")
    async def phi_fc30(self, event: AstrMessageEvent):
        """查看 Full Combo 模式下的 Top N 成绩。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'fc30')

    @phi.command('gbbind', alias={'gb\u7ed1\u5b9a'}, desc="按国际服方式绑定账号或查询 ID。")
    async def phi_gbbind(self, event: AstrMessageEvent):
        """按国际服方式绑定账号或查询 ID。"""
        yield await self._dispatch_phi_command(event, 'gbbind')

    @phi.command('guess', alias={'\u731c\u66f2\u7ed8'}, desc="开始猜曲绘小游戏，或回答当前猜歌。")
    async def phi_guess(self, event: AstrMessageEvent):
        """开始猜曲绘小游戏，或回答当前猜歌。"""
        yield await self._dispatch_phi_command(event, 'guess')

    @phi.command('help', alias={'\u547d\u4ee4', '\u5e2e\u52a9', '\u6307\u4ee4', '\u83dc\u5355'}, desc="查看 Phi-Plugin 帮助菜单。")
    async def phi_help(self, event: AstrMessageEvent):
        """查看 Phi-Plugin 帮助菜单。"""
        yield await self._dispatch_phi_command(event, 'help')

    @phi.command('hisb30', desc="查看历史 B30 变化记录。")
    async def phi_hisb30(self, event: AstrMessageEvent):
        """查看历史 B30 变化记录。"""
        yield await self._dispatch_phi_command(event, 'hisb30')

    @phi.command('2025history', alias={'\u5e74\u5ea6\u603b\u7ed3'}, desc="查看 2025 年度总结。")
    async def phi_history2025(self, event: AstrMessageEvent):
        """查看 2025 年度总结。"""
        yield await self._dispatch_phi_command(event, '2025history')

    @phi.command('id', alias={'apiid', 'uid', '\u67e5\u8be2id'}, desc="查看当前绑定的查询 ID、PlayerId 与玩家名。")
    async def phi_id(self, event: AstrMessageEvent):
        """查看当前绑定的查询 ID、PlayerId 与玩家名。"""
        yield await self._dispatch_phi_command(event, 'id')

    @phi.command('ill', alias={'\u66f2\u7ed8'}, desc="查看指定曲目的曲绘。")
    async def phi_ill(self, event: AstrMessageEvent):
        """查看指定曲目的曲绘。"""
        yield await self._dispatch_phi_command(event, 'ill')

    @phi.command('info', desc="查看玩家信息总览面板。")
    async def phi_info(self, event: AstrMessageEvent):
        """查看玩家信息总览面板。"""
        yield await self._dispatch_phi_command(event, 'info')

    @phi.command('info1', desc="查看玩家信息面板第一页。")
    async def phi_info1(self, event: AstrMessageEvent):
        """查看玩家信息面板第一页。"""
        yield await self._dispatch_phi_command(event, 'info1')

    @phi.command('info2', desc="查看玩家信息面板第二页。")
    async def phi_info2(self, event: AstrMessageEvent):
        """查看玩家信息面板第二页。"""
        yield await self._dispatch_phi_command(event, 'info2')

    @phi.command('jrrp', alias={'\u4eca\u65e5\u4eba\u54c1'}, desc="抽取今日人品与推荐曲目。")
    async def phi_jrrp(self, event: AstrMessageEvent):
        """抽取今日人品与推荐曲目。"""
        yield await self._dispatch_phi_command(event, 'jrrp')

    @phi.command('list', desc="按条件筛选并列出成绩。")
    async def phi_list(self, event: AstrMessageEvent):
        """按条件筛选并列出成绩。"""
        yield await self._dispatch_phi_command(event, 'list')

    @phi.command('live', desc="查看在线服务状态与公告信息。")
    async def phi_live(self, event: AstrMessageEvent):
        """查看在线服务状态与公告信息。"""
        yield await self._dispatch_phi_command(event, 'live')

    @phi.command('lmtacc', desc="按 ACC 下限筛选成绩并计算 RKS。")
    async def phi_lmtacc(self, event: AstrMessageEvent):
        """按 ACC 下限筛选成绩并计算 RKS。"""
        yield await self._dispatch_phi_command(event, 'lmtacc')

    @phi.command('ltr', alias={'letter', '\u5f00\u5b57\u6bcd'}, desc="开始开字母猜歌小游戏或回答指定编号。")
    async def phi_ltr(self, event: AstrMessageEvent):
        """开始开字母猜歌小游戏或回答指定编号。"""
        yield await self._dispatch_phi_command(event, 'ltr')

    @phi.command('lvscore', alias={'lvsco', 'scolv'}, desc="查看指定等级范围内的成绩。")
    async def phi_lvscore(self, event: AstrMessageEvent):
        """查看指定等级范围内的成绩。"""
        yield await self._dispatch_phi_command(event, 'lvscore')

    @phi.command('mycmt', desc="查看自己发布的在线评论。")
    async def phi_mycmt(self, event: AstrMessageEvent):
        """查看自己发布的在线评论。"""
        yield await self._dispatch_phi_command(event, 'mycmt')

    @phi.command('myset', alias={'mysetting', '\u7528\u6237\u8bbe\u7f6e', '\u4e2a\u4eba\u8bbe\u7f6e'}, desc="查看或修改个人插件设置。")
    async def phi_myset(self, event: AstrMessageEvent):
        """查看或修改个人插件设置。"""
        yield await self._dispatch_phi_command(event, 'myset')

    @phi.command('newlog', desc="查看 Phigros 最新版本更新日志。")
    async def phi_newlog(self, event: AstrMessageEvent):
        """查看 Phigros 最新版本更新日志。"""
        yield await self._dispatch_phi_command(event, 'newlog')

    @phi.command('newnotice', desc="查看 Phigros 最新公告。")
    async def phi_newnotice(self, event: AstrMessageEvent):
        """查看 Phigros 最新公告。"""
        yield await self._dispatch_phi_command(event, 'newnotice')

    @phi.command('open', alias={'\u63ed\u5f00', '\u6253\u5f00', '\u7ffb\u5f00', '\u5f00'}, desc="在开字母猜歌中翻开指定字符。")
    async def phi_open(self, event: AstrMessageEvent):
        """在开字母猜歌中翻开指定字符。"""
        yield await self._dispatch_phi_command(event, 'open')

    @phi.command('p30', alias=_P_ALIASES, desc="查看 All Perfect 模式下的 Top N 成绩。")
    async def phi_p30(self, event: AstrMessageEvent):
        """查看 All Perfect 模式下的 Top N 成绩。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'p30')

    @phi.command('pgr', alias={'\u5c41\u80a1\u8089'}, desc="查看当前绑定玩家的 B30/RKS 成绩面板。")
    async def phi_pgr(self, event: AstrMessageEvent):
        """查看当前绑定玩家的 B30/RKS 成绩面板。"""
        yield await self._dispatch_phi_command(event, 'pgr')

    @phi.command('rand', alias={'random', '\u968f\u673a'}, desc="随机抽取一首曲目或谱面。")
    async def phi_rand(self, event: AstrMessageEvent):
        """随机抽取一首曲目或谱面。"""
        yield await self._dispatch_phi_command(event, 'rand')

    @phi.command('randclg', desc="生成随机课题组。")
    async def phi_randclg(self, event: AstrMessageEvent):
        """生成随机课题组。"""
        yield await self._dispatch_phi_command(event, 'randclg')

    @phi.command('rankfind', alias={'\u67e5\u8be2\u6392\u540d'}, desc="按 RKS 查询大致排行榜位置。")
    async def phi_rankfind(self, event: AstrMessageEvent):
        """按 RKS 查询大致排行榜位置。"""
        yield await self._dispatch_phi_command(event, 'rankfind')

    @phi.command('ranklist', alias={'\u6392\u884c\u699c'}, desc="查看 RKS 排行榜或自己的排名。")
    async def phi_ranklist(self, event: AstrMessageEvent):
        """查看 RKS 排行榜或自己的排名。"""
        yield await self._dispatch_phi_command(event, 'ranklist')

    @phi.command('recmt', desc="删除自己发布的在线评论。")
    async def phi_recmt(self, event: AstrMessageEvent):
        """删除自己发布的在线评论。"""
        yield await self._dispatch_phi_command(event, 'recmt')

    @phi.command('renderdiag', alias={'\u6e32\u67d3\u8bca\u65ad'}, desc="查看 HTML/T2I 渲染诊断信息。")
    async def phi_renderdiag(self, event: AstrMessageEvent):
        """查看 HTML/T2I 渲染诊断信息。"""
        yield await self._dispatch_phi_command(event, 'renderdiag')

    @phi.command('rks', desc="查询玩家当前 RKS 信息。")
    async def phi_rks(self, event: AstrMessageEvent):
        """查询玩家当前 RKS 信息。"""
        yield await self._dispatch_phi_command(event, 'rks')

    @phi.command('retask', alias={'\u5237\u65b0\u4efb\u52a1'}, desc="刷新今日任务。")
    async def phi_retask(self, event: AstrMessageEvent):
        """刷新今日任务。"""
        yield await self._dispatch_phi_command(event, 'retask')

    @phi.command('score', alias={'\u5355\u66f2\u6210\u7ee9'}, desc="查询指定曲目的单曲成绩。")
    async def phi_score(self, event: AstrMessageEvent):
        """查询指定曲目的单曲成绩。"""
        yield await self._dispatch_phi_command(event, 'score')

    @phi.command('search', alias={'\u67e5\u627e', '\u68c0\u7d22'}, desc="搜索曲目。")
    async def phi_search(self, event: AstrMessageEvent):
        """搜索曲目。"""
        yield await self._dispatch_phi_command(event, 'search')

    @phi.command('sessiontoken', alias={'tk', 'token'}, desc="查看本地 sessionToken 绑定状态与帮助。")
    async def phi_sessiontoken(self, event: AstrMessageEvent):
        """查看本地 sessionToken 绑定状态与帮助。"""
        yield await self._dispatch_phi_command(event, 'sessiontoken')

    @phi.command('send', alias={'\u9001', '\u8f6c'}, desc="向其他用户转账 Notes。")
    async def phi_send(self, event: AstrMessageEvent):
        """向其他用户转账 Notes。"""
        yield await self._dispatch_phi_command(event, 'send')

    @phi.command('setapitoken', desc="设置查分平台 API Token。")
    async def phi_setapitoken(self, event: AstrMessageEvent):
        """设置查分平台 API Token。"""
        yield await self._dispatch_phi_command(event, 'setapitoken')

    @phi.command('setnick', alias={'setnic', '\u8bbe\u7f6e\u522b\u540d'}, desc="为曲目设置自定义别名。")
    async def phi_setnick(self, event: AstrMessageEvent):
        """为曲目设置自定义别名。"""
        yield await self._dispatch_phi_command(event, 'setnick')

    @phi.command('settag', desc="为谱面设置或投票标签。")
    async def phi_settag(self, event: AstrMessageEvent):
        """为谱面设置或投票标签。"""
        yield await self._dispatch_phi_command(event, 'settag')

    @phi.command('song', alias={'\u66f2'}, desc="查询曲目基础信息。")
    async def phi_song(self, event: AstrMessageEvent):
        """查询曲目基础信息。"""
        yield await self._dispatch_phi_command(event, 'song')

    @phi.command('sign', alias={'signin', '\u7b7e\u5230', '\u6253\u5361'}, desc="每日签到领取 Notes。")
    async def phi_sign(self, event: AstrMessageEvent):
        """每日签到领取 Notes。"""
        yield await self._dispatch_phi_command(event, 'sign')

    @phi.command('suggest', alias={'\u63a8\u5206', '\u63a8\u5206\u5efa\u8bae'}, desc="根据当前成绩生成推分建议。")
    async def phi_suggest(self, event: AstrMessageEvent):
        """根据当前成绩生成推分建议。"""
        yield await self._dispatch_phi_command(event, 'suggest')

    @phi.command('table', alias={'\u5b9a\u6570\u8868'}, desc="查询定数表。")
    async def phi_table(self, event: AstrMessageEvent):
        """查询定数表。"""
        yield await self._dispatch_phi_command(event, 'table')

    @phi.command('tag', desc="查询谱面标签统计。")
    async def phi_tag(self, event: AstrMessageEvent):
        """查询谱面标签统计。"""
        yield await self._dispatch_phi_command(event, 'tag')

    @phi.command('task', alias={'tasks', '\u6211\u7684\u4efb\u52a1'}, desc="查看今日任务与完成进度。")
    async def phi_task(self, event: AstrMessageEvent):
        """查看今日任务与完成进度。"""
        yield await self._dispatch_phi_command(event, 'task')

    @phi.command('tips', desc="随机查看一条 Phigros 小提示。")
    async def phi_tips(self, event: AstrMessageEvent):
        """随机查看一条 Phigros 小提示。"""
        yield await self._dispatch_phi_command(event, 'tips')

    @phi.command('tokenlist', alias={'tkls', 'lstk'}, desc="查看查分平台 Token 列表。")
    async def phi_tokenlist(self, event: AstrMessageEvent):
        """查看查分平台 Token 列表。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'tokenlist')

    @phi.command('tip', alias={'\u63d0\u793a'}, desc="获取当前小游戏提示。")
    async def phi_tip(self, event: AstrMessageEvent):
        """获取当前小游戏提示。"""
        yield await self._dispatch_phi_command(event, 'tip')

    @phi.command('tipgame', alias={'\u63d0\u793a\u731c\u66f2'}, desc="开始提示猜歌小游戏。")
    async def phi_tipgame(self, event: AstrMessageEvent):
        """开始提示猜歌小游戏。"""
        yield await self._dispatch_phi_command(event, 'tipgame')

    @phi.command('theme', desc="设置或查看个人渲染主题。")
    async def phi_theme(self, event: AstrMessageEvent):
        """设置或查看个人渲染主题。"""
        yield await self._dispatch_phi_command(event, 'theme')

    @phi.command('unbind', alias={'\u89e3\u7ed1'}, desc="解绑账号并清理当前用户缓存。")
    async def phi_unbind(self, event: AstrMessageEvent):
        """解绑账号并清理当前用户缓存。"""
        yield await self._dispatch_phi_command(event, 'unbind')

    @phi.command('update', alias={'\u66f4\u65b0\u5b58\u6863'}, desc="同步存档并查看最近进步情况。")
    async def phi_update(self, event: AstrMessageEvent):
        """同步存档并查看最近进步情况。"""
        yield await self._dispatch_phi_command(event, 'update')

    @phi.command('x30', alias=_X_ALIASES, desc="查看 1 Good 模式下的 Top N 成绩。")
    async def phi_x30(self, event: AstrMessageEvent):
        """查看 1 Good 模式下的 Top N 成绩。"""
        yield await self._dispatch_phi_command(event, self._extract_group_command(event.get_message_str()) or 'x30')

    @filter.event_message_type(filter.EventMessageType.ALL, priority=10)
    @filter.custom_filter(ActivePhiGameFilter, False)
    async def phi_game_reply_listener(self, event: AstrMessageEvent):
        if not self.plugin_config.game_reply_listener:
            return
        message = (event.get_message_str() or "").strip()
        if not message or message.casefold().startswith("phi "):
            return
        sender_id = event.get_sender_id()
        event.stop_event()
        result = await self._run_with_command_locks(
            event,
            sender_id,
            "__game_reply__",
            lambda: self._handle_game_reply(event, sender_id, message),
        )
        if result is None:
            return
        yield await self._send_command_result(event, result)

    async def _dispatch_phi_command(self, event: AstrMessageEvent, command: str, *, grouped: bool = True):
        event.stop_event()
        args = self._extract_command_args(event.get_message_str(), grouped=grouped)

        sender_id = event.get_sender_id()
        return await self._run_with_command_locks(
            event,
            sender_id,
            command,
            lambda: self._run_phi_command(event, sender_id, command, args),
        )

    async def _run_with_command_locks(
        self,
        event: AstrMessageEvent,
        sender_id: str,
        command: str,
        action: Callable[[], Awaitable[Any]],
    ):
        async def run_after_user_lock():
            if self._uses_game_session_lock(command):
                return await self._game_session_locks.run(self._game_lock_key(event), action)
            return await action()

        return await self._user_command_locks.run(self._user_lock_key(sender_id), run_after_user_lock)

    async def _handle_game_reply(self, event: AstrMessageEvent, sender_id: str, message: str) -> CommandResult | None:
        command_context = self._command_context_for_event(event, sender=self._event_sender(event))
        return await handle_game_reply(command_context, sender_id, message)

    async def _run_phi_command(self, event: AstrMessageEvent, sender_id: str, command: str, args: str):
        command_context = self._command_context_for_event(event, sender=self._event_sender(event))
        result = await dispatch(command_context, sender_id, command, args)
        return await self._send_command_result(event, result)

    def _event_sender(self, event: AstrMessageEvent) -> Callable[[CommandResult], Awaitable[None]]:
        async def send_intermediate(result: CommandResult) -> None:
            if result.kind == "image":
                await self._send_image_with_fallback(event, result.value)
                return
            await event.send(event.plain_result(result.value))

        return send_intermediate

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
    def _user_lock_key(sender_id: str) -> str:
        return f"user:{sender_id}"

    @classmethod
    def _game_lock_key(cls, event: AstrMessageEvent) -> str:
        session_id = cls._event_session_id(event)
        return f"game:{session_id}"

    @staticmethod
    def _uses_game_session_lock(command: str) -> bool:
        return command.casefold() in _GAME_STATE_COMMANDS or command == "__game_reply__"

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
