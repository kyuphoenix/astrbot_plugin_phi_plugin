from __future__ import annotations

from ._rendering import render_original_html
from ._user_settings import (
    build_setting_panel_data,
    normalize_settings,
    parse_setting_update,
    setting_success_message,
)
from .common import CommandContext, CommandResult
from ..render import original

ALIASES = {"myset", "mysetting", "用户设置", "个人设置"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    settings = normalize_settings(ctx.store.load_user_settings(user_id))
    if args.strip():
        key, value_or_error = parse_setting_update(args)
        if key is None:
            return CommandResult.text(value_or_error)
        value = value_or_error
        settings[key] = value == "true" if key == "allowApiUsage" else value
        ctx.store.save_user_settings(user_id, settings)
        if ctx.config.render_mode != "image":
            return CommandResult.text(setting_success_message(key, value))

    data = build_setting_panel_data(settings)
    if ctx.config.render_mode == "image":
        return CommandResult.image(await render_original_html(ctx, original.user_setting_html(ctx.paths, data), "myset"))
    return CommandResult.text(_text_settings(data))


def _text_settings(data: dict) -> str:
    lines = [str(data.get("pageTitle") or "Phi-Plugin 用户设置")]
    for item in data.get("items", []):
        lines.append(f"{item['title']}: {item['currentTitle']}")
    lines.append("修改示例：phi myset 主题 star")
    return "\n".join(lines)
