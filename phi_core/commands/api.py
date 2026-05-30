from __future__ import annotations

from .common import CommandContext, CommandResult

ALIASES = {"api"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if args.strip().casefold() in {"help", "命令", "帮助", "菜单", "说明", "功能", "指令", "使用说明"}:
        return CommandResult.text(API_HELP_TEXT)
    return CommandResult.text("请使用 phi api help 查看查分平台 API 相关帮助。")


API_HELP_TEXT = """
Phi API 帮助

当前 AstrBot 迁移版已支持：
phi bind <sessionToken|查询ID|qrcode> - 绑定并自动同步玩家数据
phi auth <API Token> - 使用查分平台 API Token 换取并保存 sessionToken
phi id - 查看当前绑定的查询 ID / PlayerId
phi tk - 查看本地 sessionToken 脱敏信息
phi myset API开关 开/关 - 配置本地是否允许使用在线 API 功能

尚未迁移的原版 API 管理命令：
setApiToken / tkls / tokenManage / clearApiData / updateHistory / updateUserToken / updateComment / apiset

这些命令涉及远端账户权限、批量上传或敏感数据管理，后续会按单独批次迁移。
""".strip()
