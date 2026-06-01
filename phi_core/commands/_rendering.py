from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .common import CommandContext
from ._user_settings import normalize_settings
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
    render_data = _apply_user_theme(ctx, template_path, dict(data or {}))
    if _selected_theme(render_data) == "dss2" and template_path.replace("\\", "/").removesuffix(".html") == "b19/b19":
        template_path = "b19/dss2"
    prepared = jinja_adapter.adapt_template_data(ctx.paths, template_path, render_data)
    template, render_data, viewport_width, viewport_height = jinja_renderer.render_template_payload(
        ctx.paths,
        template_path,
        prepared,
        width=width,
        height=height,
    )
    return await render_original_html(
        ctx,
        template,
        name,
        data=render_data,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def _apply_user_theme(ctx: CommandContext, template_path: str, data: dict[str, Any]) -> dict[str, Any]:
    if template_path.replace("\\", "/").removesuffix(".html") == "setting/userSetting":
        return data
    theme = _current_theme(ctx)
    if theme == "default":
        data.setdefault("theme", "default")
        return data
    if str(data.get("theme") or "default") in {"", "default", "common"}:
        data["theme"] = theme
    return data


def _current_theme(ctx: CommandContext) -> str:
    if not ctx.current_user_id:
        return "default"
    return str(normalize_settings(ctx.store.load_user_settings(ctx.current_user_id)).get("theme") or "default")


def _selected_theme(data: dict[str, Any]) -> str:
    return str(data.get("theme") or "default")


async def render_original_html(
    ctx: CommandContext,
    html: str,
    name: str,
    *,
    data: dict[str, Any] | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
) -> Path:
    viewport_width = viewport_width or _viewport_value(html, "--phi-viewport-width")
    viewport_height = viewport_height or _viewport_value(html, "--phi-viewport-height")
    return await panel.render_html(
        ctx.config,
        ctx.paths,
        html,
        name,
        html_render=ctx.html_render,
        data=data,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def _viewport_value(html: str, name: str) -> int | None:
    match = re.search(rf"{re.escape(name)}\s*:\s*(\d+)px", html)
    if not match:
        return None
    return int(match.group(1))
