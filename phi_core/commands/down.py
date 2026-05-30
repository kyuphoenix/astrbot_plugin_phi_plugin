from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data.ill_download import update_illustrations

ALIASES = {"down", "download", "illupdate", "downill", "下载", "下载曲绘", "更新曲绘"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    text = args.strip().casefold()
    if text and text not in {"ill", "曲绘", "original_ill", "illustration", "illustrations"}:
        return CommandResult.text("格式：phi down ill\n用途：下载或更新原版曲绘资源。")
    try:
        result = await update_illustrations(ctx.config, ctx.paths)
    except Exception as exc:
        return CommandResult.text(f"曲绘文件下载/更新失败：{exc}")
    return CommandResult.text(
        f"曲绘文件{result.action}完成。\n"
        f"版本: {result.commit}\n"
        "曲绘已保存到 AstrBot 插件数据目录，后续渲染会优先使用这里的 original_ill。"
    )
