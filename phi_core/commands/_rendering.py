from __future__ import annotations

import re
from pathlib import Path

from .common import CommandContext
from ..render import panel


async def render_original_html(ctx: CommandContext, html: str, name: str) -> Path:
    viewport_width = _viewport_value(html, "--phi-viewport-width")
    viewport_height = _viewport_value(html, "--phi-viewport-height")
    return await panel.render_html(
        ctx.config,
        ctx.paths,
        html,
        name,
        html_render=ctx.html_render,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def _viewport_value(html: str, name: str) -> int | None:
    match = re.search(rf"{re.escape(name)}\s*:\s*(\d+)px", html)
    if not match:
        return None
    return int(match.group(1))
