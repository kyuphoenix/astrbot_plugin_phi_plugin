from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..data.illustrations import is_online_illustration_url, use_remote_illustrations
from ..paths import PluginPaths
from . import original

_LINK_STYLESHEET_RE = re.compile(
    r"<link\b(?=[^>]*\brel=[\"']stylesheet[\"'])(?=[^>]*\bhref=[\"'](?P<href>[^\"']+)[\"'])[^>]*>",
    re.IGNORECASE,
)
_SCRIPT_SRC_RE = re.compile(
    r"<script\b(?=[^>]*\bsrc=[\"'](?P<src>[^\"']+)[\"'])[^>]*>\s*</script>",
    re.IGNORECASE,
)
_RES_ATTR_RE = re.compile(r"(?P<prefix>\b(?:src|href)=[\"'])(?P<url>[^\"']+)(?P<suffix>[\"'])", re.IGNORECASE)
_RES_URL_RE = re.compile(r"url\((?P<quote>[\"']?)(?P<url>[^)\"']+)(?P=quote)\)", re.IGNORECASE)
_CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\()?['\"](?P<url>[^'\")]+)['\"]\)?\s*;", re.IGNORECASE)
_VIEWPORT_RE = re.compile(r"<meta\b(?=[^>]*\bname=[\"']viewport[\"'])(?=[^>]*\bcontent=[\"'](?P<content>[^\"']*)[\"'])[^>]*>", re.IGNORECASE)

_DEFAULT_WIDTH = 1200


def render_template(
    paths: PluginPaths,
    template_path: str,
    data: Mapping[str, Any] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Render a converted upstream Jinja2 template into self-contained HTML for remote t2i."""
    root = template_root(paths)
    env = _environment(root)
    normalized = _normalize_template_path(template_path)
    context = _base_context(paths)
    if data:
        context.update(copy.deepcopy(dict(data)))
    if width is not None:
        context["_viewport_width"] = int(width)
    if height is not None:
        context["_viewport_height"] = int(height)
    rendered = env.get_template(normalized).render(**context)
    return make_self_contained(
        paths,
        root,
        rendered,
        width=int(context.get("_viewport_width") or _DEFAULT_WIDTH),
        height=int(context["_viewport_height"]) if context.get("_viewport_height") is not None else None,
    )


def make_self_contained(paths: PluginPaths, root: Path, html: str, *, width: int = _DEFAULT_WIDTH, height: int | None = None) -> str:
    html = _inline_stylesheets(paths, root, html)
    html = _inline_scripts(paths, root, html)
    html = _inline_resource_attributes(paths, root, html)
    html = _inline_css_urls(paths, root, html)
    html = _apply_viewport_width(html, width)
    html = _inject_reset_css(paths, html, width=width, height=height)
    html = _inject_auto_font_script(html)
    return html


def template_root(paths: PluginPaths) -> Path:
    candidates = [
        paths.downloads / "html",
        paths.downloads / "jinja2",
        paths.data_dir / "jinja2",
        paths.root / "jinja2",
        paths.root / "resources" / "jinja2",
        Path(r"D:\astrbot_plugin_phi_plugin\jinja2"),
    ]
    for candidate in candidates:
        if (candidate / "common" / "layout" / "default.html").exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _environment(root: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(root)),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def _normalize_template_path(template_path: str) -> str:
    normalized = str(template_path).replace("\\", "/").strip("/")
    if not normalized.endswith(".html"):
        normalized = f"{normalized}.html"
    return normalized


def _base_context(paths: PluginPaths) -> dict[str, Any]:
    return {
        "_res_path": "",
        "_plugin": "AstrBot Phi Plugin",
        "Version": {"ver": "HTML"},
        "theme": "default",
        "element": "hydro",
        "elem": "hydro",
        "displayMode": "default",
        "mode": "default",
        "bodyClass": "",
        "background": original.asset_uri(paths, "html/otherimg/phigros.png"),
        "sys": {"scale": "", "copyright": ""},
        "_viewport_width": _DEFAULT_WIDTH,
        "_viewport_height": None,
    }


def _inline_stylesheets(paths: PluginPaths, root: Path, html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        href = match.group("href")
        relative = _resource_relative(href)
        if relative is None:
            return match.group(0)
        css = _css_text(paths, root, relative)
        return f"<style>{css}</style>" if css else ""

    return _LINK_STYLESHEET_RE.sub(replace, html)


def _inline_scripts(paths: PluginPaths, root: Path, html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        src = match.group("src")
        relative = _resource_relative(src)
        if relative is None:
            return match.group(0)
        script = _read_text_resource(paths, root, relative)
        return f"<script>{script}</script>" if script else ""

    return _SCRIPT_SRC_RE.sub(replace, html)


def _inline_resource_attributes(paths: PluginPaths, root: Path, html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group("url")
        data_uri = _data_uri(paths, root, url)
        if data_uri is None:
            return match.group(0)
        return f"{match.group('prefix')}{data_uri}{match.group('suffix')}"

    return _RES_ATTR_RE.sub(replace, html)


def _inline_css_urls(paths: PluginPaths, root: Path, html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group("url").strip()
        if url.startswith("#") or url.lower().startswith("data:"):
            return match.group(0)
        data_uri = _data_uri(paths, root, url)
        if data_uri is None:
            return match.group(0)
        return f'url("{data_uri}")'

    return _RES_URL_RE.sub(replace, html)


def _apply_viewport_width(html: str, width: int) -> str:
    def replace(match: re.Match[str]) -> str:
        content = match.group("content")
        if "width=" in content:
            content = re.sub(r"width\s*=\s*[^,]+", f"width={width}", content)
        else:
            content = f"width={width},{content}" if content else f"width={width}"
        return f'<meta name="viewport" content="{content}">'

    if _VIEWPORT_RE.search(html):
        return _VIEWPORT_RE.sub(replace, html, count=1)
    return html.replace("<head>", f'<head>\n<meta name="viewport" content="width={width}">', 1)


def _inject_reset_css(paths: PluginPaths, html: str, *, width: int, height: int | None = None) -> str:
    height_var = f"--phi-viewport-height: {int(height)}px;" if height is not None else ""
    style = f"<style>:root {{--phi-viewport-width: {int(width)}px;{height_var}}}\n{original._render_reset_css('data:image/placeholder;base64,', width=width)}</style>"
    if "</head>" in html:
        return html.replace("</head>", f"{style}\n</head>", 1)
    return f"{style}\n{html}"


def _inject_auto_font_script(html: str) -> str:
    script = f"<script>{original._auto_font_script()}</script>"
    if "</body>" in html:
        return html.replace("</body>", f"{script}\n</body>", 1)
    return f"{html}\n{script}"


def _resource_relative(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith(("data:", "#", "javascript:")):
        return None
    if lowered.startswith(("http://", "https://", "file://", "base64://")):
        return None
    text = text.replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    while text.startswith("../"):
        text = text[3:]
    if text.startswith("/"):
        text = text.lstrip("/")
    if text.startswith("html/"):
        return text
    return text


def _data_uri(paths: PluginPaths, root: Path, value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("data:"):
        return text
    if lowered.startswith(("http://", "https://")) and use_remote_illustrations(paths) and is_online_illustration_url(text):
        return text
    if lowered.startswith(("base64://", "http://", "https://", "file://")):
        uri = original.image_data_uri(paths, text)
        return uri or None
    relative = _resource_relative(text)
    if relative is None:
        return None
    path = _resolve_resource_path(paths, root, relative)
    if path is None:
        return None
    uri = original.image_data_uri(paths, path)
    return uri or None


def _css_text(paths: PluginPaths, root: Path, relative: str) -> str:
    css_path = _resolve_resource_path(paths, root, relative)
    if css_path is None or not css_path.exists():
        return ""
    css = css_path.read_text(encoding="utf-8")

    def replace_import(match: re.Match[str]) -> str:
        url = unquote(match.group("url").strip())
        resolved = _resolve_relative_to_file(paths, root, css_path, url)
        if resolved is None or not resolved.exists():
            return ""
        return _css_text_from_file(paths, root, resolved)

    def replace(match: re.Match[str]) -> str:
        url = unquote(match.group("url").strip())
        if url.startswith("#") or url.lower().startswith("data:"):
            return match.group(0)
        if url.lower().startswith(("http://", "https://")) and use_remote_illustrations(paths) and is_online_illustration_url(url):
            return f'url("{url}")'
        normalized_url = url.replace("\\", "/").lower()
        if normalized_url.endswith("/otherimg/phigros.png") or normalized_url == "../otherimg/phigros.png":
            return 'url("")'
        resolved = _resolve_relative_to_file(paths, root, css_path, url)
        uri = original.image_data_uri(paths, resolved) if resolved is not None else ""
        if not uri:
            return 'url("")'
        return f'url("{uri}")'

    css = _CSS_IMPORT_RE.sub(replace_import, css)
    return _RES_URL_RE.sub(replace, css)


def _css_text_from_file(paths: PluginPaths, root: Path, css_path: Path) -> str:
    try:
        relative = css_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            relative = css_path.resolve().relative_to((paths.resources / "html").resolve()).as_posix()
        except ValueError:
            return css_path.read_text(encoding="utf-8")
    return _css_text(paths, root, relative)


def _read_text_resource(paths: PluginPaths, root: Path, relative: str) -> str:
    path = _resolve_resource_path(paths, root, relative)
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _resolve_resource_path(paths: PluginPaths, root: Path, relative: str) -> Path | None:
    normalized = relative.replace("\\", "/").lstrip("/")
    candidates: list[Path] = []
    if normalized.startswith("html/"):
        suffix = normalized[len("html/"):]
        candidates.extend([root / suffix, paths.resources / normalized])
    else:
        candidates.extend([root / normalized, paths.resources / normalized])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else None


def _resolve_relative_to_file(paths: PluginPaths, root: Path, base_file: Path, relative: str) -> Path | None:
    normalized = relative.replace("\\", "/").lstrip("/")
    candidates = [(base_file.parent / normalized)]
    try:
        template_rel = base_file.resolve().relative_to(root.resolve()).parent.as_posix()
        candidates.append(paths.resources / "html" / template_rel / normalized)
    except ValueError:
        pass
    if normalized.startswith("html/"):
        candidates.append(paths.resources / normalized)
        candidates.append(root / normalized[len("html/"):])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else None
