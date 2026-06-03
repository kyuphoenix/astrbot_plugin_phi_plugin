from __future__ import annotations

import copy
import base64
import hashlib
import logging
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..data.illustrations import is_online_illustration_url, use_remote_illustrations
from ..paths import PluginPaths
from . import original

logger = logging.getLogger("astrbot")

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
_BODY_OPEN_RE = re.compile(r"<body\b[^>]*>", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)
_CONTAINER_ID_RE = re.compile(r"\bid=[\"']container[\"']", re.IGNORECASE)
_BLOCK_RE = re.compile(r"{%\s*block\s+(?P<name>\w+)\s*%}(?P<body>.*?){%\s*endblock\s*%}", re.DOTALL)
_EXTENDS_RE = re.compile(r"{%\s*extends\s+[\"'](?P<path>[^\"']+)[\"']\s*%}")

_DEFAULT_WIDTH = 1200
_FONT_DATA_URI_CACHE_MAX_BYTES = 2 * 1024 * 1024
_TEXT_CACHE_MAX_BYTES = 512 * 1024


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
        font_corpus=_collect_text(context),
    )


def render_template_payload(
    paths: PluginPaths,
    template_path: str,
    data: Mapping[str, Any] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
) -> tuple[str, dict[str, Any], int, int | None]:
    """Build a self-contained Jinja2 template and data for AstrBot html_render."""
    root = template_root(paths)
    normalized = _normalize_template_path(template_path)
    context = _base_context(paths)
    if data:
        context.update(copy.deepcopy(dict(data)))
    if width is not None:
        context["_viewport_width"] = int(width)
    if height is not None:
        context["_viewport_height"] = int(height)
    template = _template_source(root, normalized)
    template = _rewrite_template_asset_fields(normalized, template)
    template = make_self_contained(
        paths,
        root,
        template,
        width=int(context.get("_viewport_width") or _DEFAULT_WIDTH),
        height=int(context["_viewport_height"]) if context.get("_viewport_height") is not None else None,
        font_corpus=_collect_text(context),
    )
    return (
        template,
        context,
        int(context.get("_viewport_width") or _DEFAULT_WIDTH),
        int(context["_viewport_height"]) if context.get("_viewport_height") is not None else None,
    )


def make_self_contained(
    paths: PluginPaths,
    root: Path,
    html: str,
    *,
    width: int = _DEFAULT_WIDTH,
    height: int | None = None,
    font_corpus: str = "",
) -> str:
    html = _inline_stylesheets(paths, root, html, font_corpus=font_corpus)
    html = _inline_scripts(paths, root, html)
    html = _inline_resource_attributes(paths, root, html)
    html = _inline_css_urls(paths, root, html)
    html = _apply_viewport_width(html, width)
    html = _ensure_screenshot_container(html)
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


def _template_source(root: Path, normalized: str) -> str:
    source = _read_text_file(root / normalized)
    match = _EXTENDS_RE.search(source)
    if not match:
        return source
    parent_path = match.group("path").replace("\\", "/").strip("/")
    parent = _read_text_file(root / parent_path)
    child_blocks = {m.group("name"): m.group("body") for m in _BLOCK_RE.finditer(source)}

    def replace(match: re.Match[str]) -> str:
        return child_blocks.get(match.group("name"), match.group("body"))

    return _BLOCK_RE.sub(replace, parent)


def _normalize_template_path(template_path: str) -> str:
    normalized = str(template_path).replace("\\", "/").strip("/")
    if not normalized.endswith(".html"):
        normalized = f"{normalized}.html"
    return normalized


def _base_context(paths: PluginPaths) -> dict[str, Any]:
    return {
        "_res_path": "",
        "_plugin": "Phi-Plugin",
        "Version": {"ver": "v0.1.0"},
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


def _rewrite_template_asset_fields(normalized: str, html: str) -> str:
    """Replace runtime-composed asset filenames with Python-prepared data fields.

    The returned string is still a Jinja2 template. Only resource expressions are
    rewritten so AstrBot receives JSON data instead of local/dynamic filenames.
    """
    replacements = {
        "{{ _res_path }}html/avatar/{{ gameuser.avatar }}.png": "{{ gameuser.avatarImg }}",
        "{{ _res_path }}html/avatar/{{ avatar }}.png": "{{ avatarImg }}",
        "{{ _res_path }}html/avatar/{{ user.avatar }}.png": "{{ user.avatarImg }}",
        "{{ _res_path }}html/avatar/{{ user.gameuser.avatar }}.png": "{{ user.gameuser.avatarImg }}",
        "{{ _res_path }}html/otherimg/{{ gameuser.ChallengeMode }}.png": "{{ gameuser.challengeImg }}",
        "{{ _res_path }}html/otherimg/{{ ChallengeMode }}.png": "{{ challengeImg }}",
        "{{ _res_path }}html/otherimg/{{ user.ChallengeMode }}.png": "{{ user.challengeImg }}",
        "{{ _res_path }}html/otherimg/{{ user.gameuser.ChallengeMode }}.png": "{{ user.gameuser.challengeImg }}",
        "{{ _res_path }}html/otherimg/{{ clg.ChallengeMode }}.png": "{{ clg.challengeImg }}",
        "{{ _res_path }}html/otherimg/{{ (user.challenge // 100)|int }}.png": "{{ user.challengeImg }}",
        "{{ _res_path }}html/otherimg/data.png": "{{ dataImg }}",
        "{{ _res_path }}html/otherimg/{{ song.Rating }}.png": "{{ song.ratingImg }}",
        "{{ _res_path }}html/otherimg/{{ rank.Rating }}.png": "{{ rank.ratingImg }}",
        "{{ _res_path }}html/otherimg/{{ user.record.Rating }}.png": "{{ user.record.ratingImg }}",
        "{{ _res_path }}html/otherimg/{{ e.Rating }}.png": "{{ e.ratingImg }}",
        "{{ _res_path }}html/otherimg/{{ rating.tot }}.png": "{{ ratingTotImg }}",
        "{{ _res_path }}html/otherimg/{{ key }}.png": "{{ ratingImgs.get(key, '') }}",
        "{{ _res_path }}html/otherimg/{{ help.img }}": "{{ help.imgSrc }}",
        "{{ _res_path }}html//avatar/{{ avatar }}.png": "{{ avatarImg }}",
        "{{ _res_path }}html//otherimg/{{ ChallengeMode }}.png": "{{ challengeImg }}",
        "{{ _res_path }}html/otherimg/phi.png": "{{ phiImg }}",
        "{{ _res_path }}html/otherimg/NEW.png": "{{ newImg }}",
        "{{ _res_path }}html//otherimg/5.png": "{{ challenge5Img }}",
        "{{ _res_path }}html/otherimg/Phigros_Icon_3.0.0.png": "{{ phigrosIconImg }}",
        "{{ _res_path }}html/otherimg/title.png": "{{ titleImg }}",
        "{{ _res_path }}html/jrrp/ShineAfter.removebg.png": "{{ shineAfterImg }}",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)

    html = html.replace("{{ _imgPath }}/{{ index }}.png", "{{ countImgs.get(index, '') }}")
    html = html.replace("{{ _imgPath }}/{{ chart.Rating }}.png", "{{ chart.ratingImg }}")
    html = html.replace("{{ _imgPath }}{{ dif.rating }}.png", "{{ dif.ratingImg }}")
    html = html.replace("{{ _imgPath }}phi.png", "{{ phiImg }}")
    html = html.replace("{{ _imgPath }}NEW.png", "{{ newImg }}")
    html = html.replace(
        "{{ _res_path ~ 'html/otherimg/' ~ (line.Rating or 'NEW') ~ '.png' }}{# html/otherimg/NEW.png #}",
        "{{ line.ratingImg }}",
    )
    if normalized in {"userinfo/userinfo.html", "userinfo/userinfo-old.html"}:
        html = _rewrite_userinfo_watermark(html)
    if normalized == "table/table.html":
        html = html.replace("<p>Constant Table</p>", '<p>{{ title.dec|default("Constant Table") }}</p>')
    return html


def _rewrite_userinfo_watermark(html: str) -> str:
    replacement = """
        <div class="createdbox">
            <div class="phi-plugin">
                <p>{{ _plugin }}<sup class="watermark-version">{{ Version.ver }}</sup></p>
            </div>
        </div>"""
    return re.sub(
        r"<div\s+class=[\"']createdbox[\"']>\s*"
        r"<div\s+class=[\"']phi-plugin[\"']>\s*<p>\s*\{\{\s*_plugin\s*\}\}\s*</p>\s*</div>\s*"
        r"<div\s+class=[\"']ver[\"']>\s*<p>\s*\{\{\s*Version\.ver\s*\}\}\s*</p>\s*</div>\s*"
        r"</div>",
        replacement,
        html,
        count=1,
        flags=re.IGNORECASE,
    )


def _inline_stylesheets(paths: PluginPaths, root: Path, html: str, *, font_corpus: str = "") -> str:
    def replace(match: re.Match[str]) -> str:
        href = match.group("href")
        relative = _resource_relative(href)
        if relative is None:
            return match.group(0)
        css = _css_text(paths, root, relative, font_corpus=font_corpus)
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


def _ensure_screenshot_container(html: str) -> str:
    if _CONTAINER_ID_RE.search(html):
        return html
    body_open = _BODY_OPEN_RE.search(html)
    body_close_matches = list(_BODY_CLOSE_RE.finditer(html))
    if body_open is None or not body_close_matches:
        return html
    body_close = body_close_matches[-1]
    body_inner = html[body_open.end():body_close.start()]
    wrapped = f'\n<div id="container" class="phi-screenshot-container">{body_inner}</div>\n'
    return f"{html[:body_open.end()]}{wrapped}{html[body_close.start():]}"


def _inject_reset_css(paths: PluginPaths, html: str, *, width: int, height: int | None = None) -> str:
    del paths
    height_var = f"--phi-viewport-height: {int(height)}px;" if height is not None else ""
    container_min_height = f"{int(height)}px" if height is not None else "100vh"
    height_css = (
        f"""
  height: {int(height)}px !important;
  min-height: {int(height)}px !important;
  max-height: {int(height)}px !important;"""
        if height is not None
        else ""
    )
    style = f"""<style>
:root {{
  --phi-viewport-width: {int(width)}px;
  {height_var}
}}
html {{
  margin: 0;
  padding: 0;
  width: {int(width)}px !important;
  min-width: {int(width)}px !important;
  max-width: {int(width)}px !important;
  background: #000;
  overflow-x: hidden !important;{height_css}
}}
body {{
  margin: 0;
  padding: 0;
  width: {int(width)}px !important;
  min-width: {int(width)}px !important;
  max-width: {int(width)}px !important;
  background: transparent !important;
  overflow-x: hidden !important;
  isolation: isolate;
}}
#container.phi-screenshot-container {{
  position: relative;
  width: {int(width)}px !important;
  min-width: {int(width)}px !important;
  max-width: {int(width)}px !important;
  min-height: {container_min_height};
  overflow-x: hidden !important;
  isolation: isolate;
}}
#container.phi-screenshot-container > .background {{
  inset: 0;
  width: 100% !important;
  height: 100% !important;
  min-height: 100% !important;
}}
.background {{
  z-index: -1 !important;
  pointer-events: none;
}}
.background img {{
  z-index: -1 !important;
}}
.createdbox .watermark-version {{
  font-size: 0.58em;
  line-height: 0;
  vertical-align: super;
  text-shadow: 0 0 20px #fff700;
}}
</style>"""
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
    text = re.sub(r"\{\{\s*_res_path\s*\}\}", "", text)
    text = re.sub(r"\{\{\s*_imgPath\s*\}\}", str(value or ""), text)
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


def _css_text(paths: PluginPaths, root: Path, relative: str, *, font_corpus: str = "") -> str:
    css_path = _resolve_resource_path(paths, root, relative)
    if css_path is None or not css_path.exists():
        return ""
    css = _read_text_file(css_path)

    def replace_import(match: re.Match[str]) -> str:
        url = unquote(match.group("url").strip())
        resolved = _resolve_relative_to_file(paths, root, css_path, url)
        if resolved is None or not resolved.exists():
            return ""
        return _css_text_from_file(paths, root, resolved, font_corpus=font_corpus)

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
        uri = _font_data_uri(paths, resolved, font_corpus=font_corpus) if _is_font_url(url, resolved) else ""
        if not uri:
            uri = original.image_data_uri(paths, resolved) if resolved is not None else ""
        if not uri:
            return 'url("")'
        return f'url("{uri}")'

    css = _CSS_IMPORT_RE.sub(replace_import, css)
    return _RES_URL_RE.sub(replace, css)


def _is_font_url(url: str, path: Path | None) -> bool:
    suffix = (path.suffix if path is not None else Path(url).suffix).lower()
    return suffix in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}


def _font_data_uri(paths: PluginPaths, font_path: Path | None, *, font_corpus: str = "") -> str:
    if font_path is None or not font_path.exists() or not font_path.is_file():
        return ""
    try:
        subset_path = _subset_font(paths, font_path, font_corpus=font_corpus)
        return _font_file_data_uri(subset_path)
    except Exception as exc:
        logger.warning("phi jinja font subset failed for %s: %s", font_path, exc)
        return _font_file_data_uri(font_path)


def _font_file_data_uri(font_path: Path) -> str:
    stat = font_path.stat()
    if stat.st_size <= _FONT_DATA_URI_CACHE_MAX_BYTES:
        return _cached_font_file_data_uri(str(font_path.resolve()), stat.st_size, stat.st_mtime_ns)
    payload = base64.b64encode(font_path.read_bytes()).decode("ascii")
    return f"data:font/ttf;base64,{payload}"


@lru_cache(maxsize=16)
def _cached_font_file_data_uri(abs_path: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    payload = base64.b64encode(Path(abs_path).read_bytes()).decode("ascii")
    return f"data:font/ttf;base64,{payload}"


def _subset_font(paths: PluginPaths, font_path: Path, *, font_corpus: str = "") -> Path:
    from fontTools import subset

    chars = _font_subset_corpus(font_corpus)
    stat = font_path.stat()
    digest = hashlib.sha1(
        f"{font_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{chars}".encode("utf-8")
    ).hexdigest()[:20]
    cache_dir = paths.cache / "fonts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output = cache_dir / f"{font_path.stem}-jinja-{digest}.ttf"
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


def _font_subset_corpus(extra: str = "") -> str:
    base = (
        "Phi Plugin Phigros AstrBot "
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
        ".,:;!?+-*/%=#()[]{}<>_&|~'\"`^ "
        "一二三四五六七八九十百千万亿年月日时分秒"
        "帮助命令玩家成绩曲绘排行统计更新信息绑定登录进步建议"
        "平均准确率分数难度等级收藏完成全连理论新增历史查询随机"
        "中文变量循环显示面板"
    )
    return "".join(sorted(set(base + (extra or ""))))


def _collect_text(value: Any) -> str:
    parts: list[str] = []

    def visit(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, str):
            lowered = item[:64].lower()
            if lowered.startswith(("data:", "base64://", "http://", "https://", "file://")):
                return
            if len(item) <= 5000:
                parts.append(item)
            return
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child)
            return
        if isinstance(item, (int, float, bool)):
            parts.append(str(item))

    visit(value)
    return "".join(parts)


def _css_text_from_file(paths: PluginPaths, root: Path, css_path: Path, *, font_corpus: str = "") -> str:
    try:
        relative = css_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            relative = css_path.resolve().relative_to((paths.resources / "html").resolve()).as_posix()
        except ValueError:
            return _read_text_file(css_path)
    return _css_text(paths, root, relative, font_corpus=font_corpus)


def _read_text_resource(paths: PluginPaths, root: Path, relative: str) -> str:
    path = _resolve_resource_path(paths, root, relative)
    if path is None or not path.exists():
        return ""
    return _read_text_file(path)


def _read_text_file(path: Path) -> str:
    stat = path.stat()
    if stat.st_size <= _TEXT_CACHE_MAX_BYTES:
        return _cached_read_text(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=256)
def _cached_read_text(abs_path: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    return Path(abs_path).read_text(encoding="utf-8")


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
