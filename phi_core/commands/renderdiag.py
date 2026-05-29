from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import image

ALIASES = {"renderdiag", "渲染诊断"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    font_path = image.selected_font_path(ctx.paths)
    panel = image.render_text_panel(
        ctx.paths,
        "\n".join(
            [
                "渲染诊断",
                f"render_mode: {ctx.config.render_mode}",
                f"resources: {ctx.paths.resources}",
                f"data_dir: {ctx.paths.data_dir}",
                f"font: {font_path}",
                "中文测试：绑定成功，请使用 phi bind qrcode 扫码登录。",
            ]
        ),
        title="Phi Render Diagnostics",
    )
    return CommandResult.image(panel)
