from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment

from ..paths import PluginPaths
from . import image as pillow_image
from . import original

WIDTH = 1200
logger = logging.getLogger("astrbot")


def backend_diagnostics(paths: PluginPaths) -> dict[str, Any]:
    return {
        "template_dir": str(paths.resources / "html"),
        "font": str(_font_path(paths)),
        "font_exists": _font_path(paths).exists(),
        "font_cache": str(_font_cache_dir(paths)),
        "renderer": "AstrBot Star.html_render",
    }


def help_html(paths: PluginPaths) -> str:
    return original.help_html(paths)


def text_html(paths: PluginPaths, text: str, title: str = "Phi Plugin") -> str:
    corpus = _collect_text([title, text, "Phi Plugin / AstrBot", "Rendered by HTML template"])
    return _render_template(paths, "panel.html", {
        "title": title,
        "lines": text.strip("\n").splitlines() or [""],
        **_asset_data(paths, corpus, title_corpus=title),
    })


def help_template_data(paths: PluginPaths) -> tuple[str, dict[str, Any]]:
    """Compatibility helper for smoke tests and older callers."""
    return help_html(paths), {}


def text_template_data(paths: PluginPaths, text: str, title: str = "Phi Plugin") -> tuple[str, dict[str, Any]]:
    """Compatibility helper for smoke tests and older callers."""
    return text_html(paths, text, title), {}


def _asset_data(paths: PluginPaths, corpus: str, *, title_corpus: str) -> dict[str, str]:
    font_path = _font_path(paths)
    title_font_path = paths.resources / "fonts" / "Aldrich-Regular.ttf"
    return {
        "font_url": _font_data_uri(paths, font_path, corpus) or _raw_font_data_uri(font_path),
        "title_font_url": _font_data_uri(paths, title_font_path, title_corpus) or _raw_font_data_uri(title_font_path),
    }


def _template(paths: PluginPaths, name: str) -> str:
    template = (_template_dir(paths) / name).read_text(encoding="utf-8")
    css = (_template_dir(paths) / "base.css").read_text(encoding="utf-8")
    return template.replace("{{ base_css }}", css)


def _render_template(paths: PluginPaths, name: str, data: dict[str, Any]) -> str:
    template = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True).from_string(_template(paths, name))
    return template.render(**data)


def _template_dir(paths: PluginPaths) -> Path:
    return paths.resources / "templates"


def _font_cache_dir(paths: PluginPaths) -> Path:
    return paths.cache / "fonts"


def _font_path(paths: PluginPaths) -> Path:
    bundled = paths.resources / "fonts" / "NotoSansSC-VF.ttf"
    if bundled.exists():
        return bundled
    for candidate in pillow_image.font_diagnostics(paths):
        path = Path(candidate)
        if path.exists():
            return path
    return bundled


def _font_data_uri(paths: PluginPaths, font_path: Path, corpus: str) -> str:
    if not font_path.exists():
        return ""
    try:
        subset_path = _subset_font(paths, font_path, corpus)
        payload = base64.b64encode(subset_path.read_bytes()).decode("ascii")
        return f"data:font/ttf;base64,{payload}"
    except Exception as exc:
        logger.warning("phi html font subset failed for %s: %s", font_path, exc)
        return ""


def _subset_font(paths: PluginPaths, font_path: Path, corpus: str) -> Path:
    from fontTools import subset

    chars = "".join(sorted(set(corpus or "Phi Plugin")))
    stat = font_path.stat()
    digest = hashlib.sha1(f"{font_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{chars}".encode("utf-8")).hexdigest()[:20]
    cache_dir = _font_cache_dir(paths)
    cache_dir.mkdir(parents=True, exist_ok=True)
    output = cache_dir / f"{font_path.stem}-{digest}.ttf"
    if output.exists() and output.stat().st_size > 0:
        return output

    options = subset.Options()
    options.flavor = None
    options.layout_features = "*"
    font = subset.load_font(str(font_path), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=chars)
    subsetter.subset(font)
    subset.save_font(font, str(output), options)
    return output


def _raw_font_data_uri(font_path: Path) -> str:
    if not font_path.exists():
        return ""
    payload = base64.b64encode(font_path.read_bytes()).decode("ascii")
    return f"data:font/ttf;base64,{payload}"


def _collect_text(*values: Any) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            parts.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
            return
        parts.append(str(value))

    for value in values:
        visit(value)
    return "\n".join(parts)
