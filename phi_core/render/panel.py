from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from pathlib import Path
import uuid

from ..config import PluginConfig
from ..paths import PluginPaths
from . import html_renderer

HtmlRenderFunc = Callable[[str, dict, bool, dict | None], Awaitable[str | bytes]]
logger = logging.getLogger("astrbot")

async def render_help_panel(config: PluginConfig, paths: PluginPaths, html_render: HtmlRenderFunc | None = None) -> Path:
    if html_render is None:
        raise RuntimeError("AstrBot html_render is not available; Pillow panel fallback has been removed.")
    try:
        rendered = await html_render(html_renderer.help_html(paths), {}, False, _options())
        result = _render_result_path(paths, rendered, "help")
        if result is not None:
            return result
        raise RuntimeError(f"AstrBot html_render returned a missing or invalid image path: {rendered!r}")
    except Exception as exc:
        logger.warning("phi html help render failed; Pillow fallback is disabled: %s", exc)
        raise


async def render_text_panel(
    config: PluginConfig,
    paths: PluginPaths,
    text: str,
    title: str = "Phi Plugin",
    html_render: HtmlRenderFunc | None = None,
) -> Path:
    if html_render is None:
        raise RuntimeError("AstrBot html_render is not available; Pillow panel fallback has been removed.")
    try:
        rendered = await html_render(html_renderer.text_html(paths, text, title=title), {}, False, _options())
        result = _render_result_path(paths, rendered, "panel")
        if result is not None:
            return result
        raise RuntimeError(f"AstrBot html_render returned a missing or invalid image path: {rendered!r}")
    except Exception as exc:
        logger.warning("phi html text render failed; Pillow fallback is disabled: %s", exc)
        raise


def render_diagnostics(config: PluginConfig, paths: PluginPaths) -> str:
    html_diag = html_renderer.backend_diagnostics(paths)
    return "\n".join(
        [
            f"render_mode: {config.render_mode}",
            f"render_backend: {config.render_backend}",
            f"resources: {paths.resources}",
            f"data_dir: {paths.data_dir}",
            f"html_template_dir: {html_diag['template_dir']}",
            f"html_font: {html_diag['font']}",
            f"html_font_exists: {html_diag['font_exists']}",
            f"html_font_cache: {html_diag['font_cache']}",
            f"html_renderer: {html_diag['renderer']}",
        ]
    )


def _options() -> dict:
    return {
        "full_page": True,
        "type": "png",
        "device_scale_factor_level": "ultra",
        "timeout": 30000,
    }


def _render_result_path(paths: PluginPaths, rendered: str | bytes, name: str) -> Path | None:
    if isinstance(rendered, bytes):
        if rendered.startswith(b"\x89PNG"):
            suffix = ".png"
        elif rendered.startswith(b"\xff\xd8"):
            suffix = ".jpg"
        else:
            logger.warning("phi html render returned non-image bytes: %r", rendered[:32])
            return None
        paths.render_cache.mkdir(parents=True, exist_ok=True)
        output = paths.render_cache / f"html-{name}-{uuid.uuid4().hex[:10]}{suffix}"
        output.write_bytes(rendered)
        return output

    result = Path(rendered)
    if result.exists():
        return result
    return None
