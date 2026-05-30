from __future__ import annotations

from pathlib import Path

from .common import CommandContext
from ..render import panel


async def render_original_html(ctx: CommandContext, html: str, name: str) -> Path:
    return await panel.render_html(
        ctx.config,
        ctx.paths,
        html,
        name,
        html_render=ctx.html_render,
    )
