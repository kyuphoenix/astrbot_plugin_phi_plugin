from __future__ import annotations

from ._user_settings import normalize_settings
from .common import CommandContext, CommandResult

ALIASES = {"theme"}

THEMES = [
    ("default", "默认"),
    ("snow", "寒冬"),
    ("star", "使一颗心免于哀伤"),
    ("dss2", "大师赛2"),
]


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    text = args.strip()
    if not text.isdigit():
        return CommandResult.text(f"请输入主题数字嗷！\n格式：phi theme 0-{len(THEMES) - 1}")
    index = int(text)
    if index < 0 or index >= len(THEMES):
        return CommandResult.text(f"请输入主题数字嗷！\n格式：phi theme 0-{len(THEMES) - 1}")
    settings = normalize_settings(ctx.store.load_user_settings(user_id))
    settings["theme"] = THEMES[index][0]
    ctx.store.save_user_settings(user_id, settings)
    return CommandResult.text(f"设置成功！\n你当前的主题是：{THEMES[index][1]}")
