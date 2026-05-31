from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .common import CommandContext
from ..render import jinja_adapter, jinja_renderer, panel


async def render_jinja_template(
    ctx: CommandContext,
    template_path: str,
    data: Mapping[str, Any] | None,
    name: str,
    *,
    width: int | None = None,
    height: int | None = None,
) -> Path:
    prepared = jinja_adapter.adapt_template_data(template_path, dict(data or {}))
    html = jinja_renderer.render_template(ctx.paths, template_path, prepared, width=width, height=height)
    return await render_original_html(ctx, html, name)


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
