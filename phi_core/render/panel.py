from __future__ import annotations

from collections.abc import Awaitable, Callable
import asyncio
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
        rendered = await _render_with_retries(config, html_render, html_renderer.help_html(paths))
        result = _render_result_path(paths, rendered, "help")
        if result is not None:
            return result
        raise RuntimeError(f"AstrBot html_render returned a missing or invalid image path: {rendered!r}")
    except Exception as exc:
        logger.warning("phi html help render failed; Pillow fallback is disabled: %s", exc)
        raise


async def render_html(
    config: PluginConfig,
    paths: PluginPaths,
    html: str,
    name: str,
    html_render: HtmlRenderFunc | None = None,
) -> Path:
    if html_render is None:
        raise RuntimeError("AstrBot html_render is not available; Pillow panel fallback has been removed.")
    try:
        rendered = await _render_with_retries(config, html_render, html)
        result = _render_result_path(paths, rendered, name)
        if result is not None:
            return result
        raise RuntimeError(f"AstrBot html_render returned a missing or invalid image path: {rendered!r}")
    except Exception as exc:
        logger.warning("phi original html render failed; Pillow fallback is disabled: %s", exc)
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
        rendered = await _render_with_retries(config, html_render, html_renderer.text_html(paths, text, title=title))
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
            f"downloaded_original_ill: {paths.downloaded_original_ill}",
            f"downloaded_illBlur_count: {_count_files(paths.downloaded_original_ill / 'illBlur')}",
            f"downloaded_illLow_count: {_count_files(paths.downloaded_original_ill / 'illLow')}",
            f"downloaded_ill_count: {_count_files(paths.downloaded_original_ill / 'ill')}",
            f"downloaded_root_ill_count: {_count_files(paths.downloaded_original_ill)}",
            f"html_template_dir: {html_diag['template_dir']}",
            f"html_font: {html_diag['font']}",
            f"html_font_exists: {html_diag['font_exists']}",
            f"html_font_cache: {html_diag['font_cache']}",
            f"html_renderer: {html_diag['renderer']}",
        ]
    )


def _count_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file())


async def _render_with_retries(config: PluginConfig, html_render: HtmlRenderFunc, html: str) -> str | bytes:
    attempts = max(1, config.render_max_retries + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await html_render(html, {}, False, _options())
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = min(0.5 * attempt, 2.0)
            logger.warning(
                "phi html render attempt %s/%s failed: %s; retrying in %.1fs",
                attempt,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


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
        return _trim_right_border(paths, output, name)

    result = Path(rendered)
    if result.exists():
        return _trim_right_border(paths, result, name)
    return None


def _trim_right_border(paths: PluginPaths, path: Path, name: str) -> Path:
    try:
        from PIL import Image

        with Image.open(path) as image:
            crop_right = _right_content_edge(image.convert("RGB"))
            if crop_right >= image.width - 1 or crop_right < int(image.width * 0.8):
                return path
            paths.render_cache.mkdir(parents=True, exist_ok=True)
            output = paths.render_cache / f"html-{name}-trim-{uuid.uuid4().hex[:10]}{path.suffix or '.png'}"
            image.crop((0, 0, crop_right + 1, image.height)).save(output)
            return output
    except Exception as exc:
        logger.warning("phi html render right-border trim skipped for %s: %s", path, exc)
    return path


def _right_content_edge(image) -> int:
    for x in range(image.width - 1, -1, -1):
        if not _is_blank_border_column(image, x):
            return x
    return image.width - 1


def _is_blank_border_column(image, x: int) -> bool:
    step = max(1, image.height // 240)
    total = 0
    black = 0
    white = 0
    for y in range(0, image.height, step):
        r, g, b = image.getpixel((x, y))[:3]
        total += 1
        if max(r, g, b) <= 18:
            black += 1
        elif min(r, g, b) >= 242:
            white += 1
    if total == 0:
        return False
    return black / total >= 0.98 or white / total >= 0.98
