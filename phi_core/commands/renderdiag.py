from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import panel

ALIASES = {"renderdiag", "渲染诊断"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    rendered = await panel.render_text_panel(
        ctx.config,
        ctx.paths,
        "\n".join(
            [
                "渲染诊断",
                panel.render_diagnostics(ctx.config, ctx.paths),
                "中文测试：绑定成功，请使用 phi bind qrcode 扫码登录。",
            ]
        ),
        title="Phi Render Diagnostics",
        html_render=ctx.html_render,
    )
    return CommandResult.image(rendered)
