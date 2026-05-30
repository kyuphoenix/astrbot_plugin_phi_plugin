from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render

ALIASES = {"sessiontoken", "token", "tk"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if args.strip().casefold() in {"help", "命令", "帮助", "菜单", "说明", "功能", "指令", "使用说明"}:
        return CommandResult.text(
            "sessionToken 有关帮助：\n"
            "【推荐】扫码登录 TapTap 获取 token\n"
            "指令：phi bind qrcode\n"
            "【基础方法】https://www.kdocs.cn/l/catqcMM9UR5Y\n"
            "绑定 sessionToken 指令：\n"
            "phi bind <sessionToken>"
        )
    return CommandResult.text(render.render_session_token(
        ctx.store.get_token(user_id),
        ctx.store.get_api_id(user_id),
    ))
