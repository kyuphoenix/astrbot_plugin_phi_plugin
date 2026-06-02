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
_TRIM_MAX_PIXELS = 48_000_000

async def render_help_panel(config: PluginConfig, paths: PluginPaths, html_render: HtmlRenderFunc | None = None) -> Path:
    if html_render is None:
        raise RuntimeError("AstrBot html_render is not available; Pillow panel fallback has been removed.")
    try:
        return await _render_with_retries(
            config,
            paths,
            html_render,
            html_renderer.help_html(paths),
            "help",
        )
    except Exception as exc:
        logger.warning("phi html help render failed; Pillow fallback is disabled: %s", exc)
        raise


async def render_html(
    config: PluginConfig,
    paths: PluginPaths,
    html: str,
    name: str,
    html_render: HtmlRenderFunc | None = None,
    data: dict | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    full_page: bool = True,
) -> Path:
    if html_render is None:
        raise RuntimeError("AstrBot html_render is not available; Pillow panel fallback has been removed.")
    try:
        return await _render_with_retries(
            config,
            paths,
            html_render,
            html,
            name,
            data=data,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            full_page=full_page,
        )
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
        return await _render_with_retries(
            config,
            paths,
            html_render,
            html_renderer.text_html(paths, text, title=title),
            "panel",
        )
    except Exception as exc:
        logger.warning("phi html text render failed; Pillow fallback is disabled: %s", exc)
        raise


def render_diagnostics(config: PluginConfig, paths: PluginPaths) -> str:
    html_diag = html_renderer.backend_diagnostics(paths)
    return "\n".join(
        [
            f"render_mode: {config.render_mode}",
            f"render_backend: {config.render_backend}",
            f"render_selector_screenshot: {config.render_selector_screenshot}",
            f"render_wait_for_resources: {config.render_wait_for_resources}",
            f"render_resource_timeout: {config.render_resource_timeout}",
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


async def _render_with_retries(
    config: PluginConfig,
    paths: PluginPaths,
    html_render: HtmlRenderFunc,
    html: str,
    name: str,
    *,
    data: dict | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    full_page: bool = True,
) -> Path:
    attempts = max(1, config.render_max_retries + 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            rendered = await html_render(
                html,
                data or {},
                False,
                _options(
                    config,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height,
                    full_page=full_page,
                ),
            )
            result = _render_result_path(paths, rendered, name)
            if result is not None:
                return result
            raise RuntimeError(
                "AstrBot html_render returned a missing or invalid image path: "
                f"{_render_result_label(rendered)}"
            )
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


def _options(
    config: PluginConfig,
    *,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
    full_page: bool = True,
) -> dict:
    options = {
        "full_page": full_page,
        "type": "png",
        "device_scale_factor_level": "ultra",
        "scale": "css",
        "timeout": 30000,
        "viewport_width": viewport_width or 1200,
        "viewport_height": viewport_height or 1000,
    }
    if config.render_selector_screenshot:
        options.update(
            {
                "selector": "#container",
                "fallback_selector": "body",
                "selector_timeout": 1000,
            }
        )
    if config.render_wait_for_resources:
        options.update(
            {
                "wait_for_resources": True,
                "resource_timeout": config.render_resource_timeout,
            }
        )
    return options


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
        if not _is_valid_image_file(output):
            return None
        return _trim_right_border(paths, output, name)

    result = Path(rendered)
    if result.exists() and _is_valid_image_file(result):
        return _trim_right_border(paths, result, name)
    return None


def _render_result_label(rendered: str | bytes) -> str:
    if isinstance(rendered, bytes):
        return f"bytes[{len(rendered)}]={rendered[:32]!r}"
    return repr(rendered)


def _is_valid_image_file(path: Path) -> bool:
    try:
        from PIL import Image

        previous_limit = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(path) as image:
                image.verify()
            return True
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit
    except Exception as exc:
        logger.warning(
            "phi html render returned invalid image file %s: %s; first_bytes=%r",
            path,
            exc,
            _read_file_head(path),
        )
        return False


def _read_file_head(path: Path, size: int = 64) -> bytes:
    try:
        with path.open("rb") as file:
            return file.read(size)
    except OSError:
        return b""


def _trim_right_border(paths: PluginPaths, path: Path, name: str) -> Path:
    try:
        from PIL import Image

        previous_limit = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(path) as image:
                if image.width * image.height > _TRIM_MAX_PIXELS:
                    logger.info(
                        "phi html render right-border trim skipped for large image %s: %sx%s",
                        path,
                        image.width,
                        image.height,
                    )
                    return path
                crop_right = _right_content_edge(image.convert("RGB"))
                if crop_right >= image.width - 1 or crop_right < int(image.width * 0.8):
                    return path
                paths.render_cache.mkdir(parents=True, exist_ok=True)
                output = paths.render_cache / f"html-{name}-trim-{uuid.uuid4().hex[:10]}{path.suffix or '.png'}"
                image.crop((0, 0, crop_right + 1, image.height)).save(output)
                return output
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit
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
