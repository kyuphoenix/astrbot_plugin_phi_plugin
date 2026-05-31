from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data.ill_download import update_illustrations, update_resources

ALIASES = {"down", "download", "illupdate", "downill", "下载", "下载曲绘", "更新曲绘"}

_ACTION_TEXT = {"download": "下载", "update": "更新"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    text = args.strip().casefold()
    if text in {"res", "resource", "resources", "资源", "html", "info"}:
        return await _download_resources(ctx)
    if text in {"all", "全部"}:
        resource = await _download_resources(ctx)
        ill = await _download_illustrations(ctx)
        return CommandResult.text(resource.value + "\n\n" + ill.value)
    if text and text not in {"ill", "曲绘", "original_ill", "illustration", "illustrations"}:
        return CommandResult.text(
            "格式：phi down resources / phi down ill / phi down all\n"
            "用途：下载或更新 Jinja2 html 模板、原版 info/otherill 与曲绘资源。"
        )
    return await _download_illustrations(ctx)


async def _download_illustrations(ctx: CommandContext) -> CommandResult:
    try:
        result = await update_illustrations(ctx.config, ctx.paths)
    except Exception as exc:
        return CommandResult.text(f"曲绘文件下载/更新失败：{exc}")
    action = _ACTION_TEXT.get(result.action, result.action)
    return CommandResult.text(
        f"曲绘文件{action}完成。\n"
        f"版本: {result.commit}\n"
        "曲绘已保存到 AstrBot 插件数据目录，后续渲染会优先使用这里的 original_ill。"
    )


async def _download_resources(ctx: CommandContext) -> CommandResult:
    try:
        result = await update_resources(ctx.config, ctx.paths)
    except Exception as exc:
        return CommandResult.text(f"资源下载/更新失败：{exc}")
    action = _ACTION_TEXT.get(result.action, result.action)
    return CommandResult.text(
        f"资源{action}完成。\n"
        f"版本: {result.commit}\n"
        f"位置: {result.target}\n"
        "已写入 downloads/html、downloads/info、downloads/otherill。\n"
        "其中 html 来自 kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template，info/otherill 暂时仍来自 Catrong/phi-plugin。"
    )
