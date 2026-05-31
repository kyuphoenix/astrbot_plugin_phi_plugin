from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

SOURCE_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\phi-plugin\resources\html")
TARGET_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\jinja2")
DOC_PATH = Path(r"D:\astrbot_plugin_phi_plugin\astrbot_plugin_phi_plugin\docs\jinja2-template-migration.md")

TOKEN_RE = re.compile(r"{{\s*(.*?)\s*}}", re.S)
EACH_RE = re.compile(r"^each\s+(.+?)(?:\s+([A-Za-z_$][\w$]*))?(?:\s+([A-Za-z_$][\w$]*))?$", re.S)
BLOCK_RE = re.compile(r"^block\s+['\"]([\w-]+)['\"]$")
EXTEND_RE = re.compile(r"^extend\s+(.+)$")
TO_FIXED_RE = re.compile(r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)\.toFixed\((\d+)\)")
INCLUDES_RE = re.compile(r"(.+?)\.includes\((.+)\)$")
REPLACE_LITERAL_RE = re.compile(r"^(.+?)\.replace\((['\"].*?['\"]),\s*(['\"].*?['\"])\)$")
OPTIONAL_CHAIN_RE = re.compile(r"([A-Za-z_$][\w$]*)\?\.")
NULLISH_RE = re.compile(r"^(.+?)\s*\?\?\s*(.+)$")
SIMPLE_TERNARY_RE = re.compile(r"^(.+?)\s*\?\s*(.+?)\s*:\s*(.+)$", re.S)
ART_ONLY_MARKERS = ("=>", "function", "new ")


def main() -> None:
    if not SOURCE_ROOT.exists():
        raise SystemExit(f"source html directory missing: {SOURCE_ROOT}")
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    converted: list[dict[str, str]] = []
    warnings: dict[str, list[str]] = {}

    for art_path in sorted(SOURCE_ROOT.rglob("*.art"), key=lambda p: p.relative_to(SOURCE_ROOT).as_posix().lower()):
        rel = art_path.relative_to(SOURCE_ROOT)
        target = TARGET_ROOT / rel.with_suffix(".html")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = art_path.read_text(encoding="utf-8-sig")
        out, file_warnings = convert_template(source)
        target.write_text(out, encoding="utf-8", newline="\n")
        rel_key = rel.as_posix()
        converted.append({
            "folder": rel.parts[0],
            "source": rel.as_posix(),
            "target": target.relative_to(TARGET_ROOT).as_posix(),
            "warnings": str(len(file_warnings)),
        })
        if file_warnings:
            warnings[rel_key] = file_warnings

    write_doc(converted, warnings)
    print(f"converted {len(converted)} .art templates into {TARGET_ROOT}")
    print(f"wrote {DOC_PATH}")


def convert_template(text: str) -> tuple[str, list[str]]:
    warnings: list[str] = []

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        if not raw:
            return ""
        directive = convert_directive(raw, warnings)
        return directive

    converted = TOKEN_RE.sub(replace, text)
    converted = converted.replace("{{/each}}", "{% endfor %}")
    converted = converted.replace("{{/if}}", "{% endif %}")
    converted = converted.replace("{{/block}}", "{% endblock %}")
    converted = "{# Generated from phi-plugin art-template syntax. Review docs/jinja2-template-migration.md before runtime use. #}\n" + converted
    return converted, warnings


def convert_directive(raw: str, warnings: list[str]) -> str:
    if raw == "/if":
        return "{% endif %}"
    if raw == "/each":
        return "{% endfor %}"
    if raw == "/block":
        return "{% endblock %}"
    if raw == "else":
        return "{% else %}"
    if raw.startswith("else if "):
        return "{% elif " + convert_condition(raw[8:].strip(), warnings) + " %}"
    if raw.startswith("if "):
        return "{% if " + convert_condition(raw[3:].strip(), warnings) + " %}"
    if raw.startswith("set "):
        assignment = raw[4:].strip()
        if "=" in assignment:
            name, value = assignment.split("=", 1)
            return "{% set " + name.strip() + " = " + convert_expr(value.strip(), warnings, allow_helper=True) + " %}"
        warnings.append(f"unresolved set: {raw}")
        return "{# FIXME unresolved art-template set: " + raw + " #}"

    block = BLOCK_RE.match(raw)
    if block:
        return "{% block " + block.group(1).replace("-", "_") + " %}"

    extend = EXTEND_RE.match(raw)
    if extend:
        name = extend.group(1).strip()
        if name == "defaultLayout":
            return '{% extends "common/layout/default.html" %}'
        if name == "elemLayout":
            return '{% extends "common/layout/elem.html" %}'
        warnings.append(f"unresolved extend: {raw}")
        return '{% extends art_expr(' + py_string(raw) + ') %}'

    each = EACH_RE.match(raw)
    if each:
        collection = convert_expr(each.group(1).strip(), warnings, allow_helper=True)
        var = (each.group(2) or "_item").replace("$", "_")
        idx = (each.group(3) or "").replace("$", "_")
        prefix = f"{{% for {var} in {collection} %}}"
        if idx:
            prefix += f"{{% set {idx} = loop.index0 %}}"
        return prefix

    if raw.startswith("@"):
        return "{{ " + convert_expr(raw[1:].strip(), warnings, allow_helper=True) + "|safe }}"
    if raw.startswith("#"):
        return "{{ " + convert_expr(raw[1:].strip(), warnings, allow_helper=True) + "|safe }}"
    return "{{ " + convert_expr(raw, warnings, allow_helper=True) + " }}"


def convert_condition(expr: str, warnings: list[str]) -> str:
    return convert_expr(expr, warnings, allow_helper=True)


def convert_expr(expr: str, warnings: list[str], *, allow_helper: bool) -> str:
    original = expr.strip()
    expr = original
    expr = expr.replace("`", "'")
    expr = expr.replace("===", "==").replace("!==", "!=")
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!\s*(?!=)\(([^()]*)\)", r"not (\1)", expr)
    expr = re.sub(r"!\s*(?!=)([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)", r"not \1", expr)
    expr = re.sub(r"\.\s*(\[[^\]]+\])", r"\1", expr)
    expr = expr.replace("$index", "loop.index0").replace("$value", "_item")
    expr = re.sub(r"\bundefined\b", "none", expr)
    expr = re.sub(r"\bnull\b", "none", expr)
    expr = re.sub(r"\btrue\b", "true", expr)
    expr = re.sub(r"\bfalse\b", "false", expr)

    nullish = NULLISH_RE.match(expr)
    if nullish:
        left = convert_expr(nullish.group(1), warnings, allow_helper=False)
        right = convert_expr(nullish.group(2), warnings, allow_helper=False)
        return f"({left}|default({right}))"

    expr = OPTIONAL_CHAIN_RE.sub(r"\1.", expr)

    # Convert simple JS ternaries after logical operator normalization.
    ternary = split_top_level_ternary(expr)
    if ternary is not None:
        cond, yes, no = ternary
        return f"({convert_expr(yes, warnings, allow_helper=False)} if {convert_expr(cond, warnings, allow_helper=False)} else {convert_expr(no, warnings, allow_helper=False)})"

    includes = INCLUDES_RE.match(expr)
    if includes:
        haystack = convert_expr(includes.group(1), warnings, allow_helper=False)
        needle = convert_expr(includes.group(2), warnings, allow_helper=False)
        return f"({needle} in {haystack})"

    replace_literal = REPLACE_LITERAL_RE.match(expr)
    if replace_literal:
        base = convert_expr(replace_literal.group(1), warnings, allow_helper=False)
        old = replace_literal.group(2)
        new = replace_literal.group(3)
        return f"({base}|replace({old}, {new}))"

    expr = TO_FIXED_RE.sub(lambda m: f"('%.{m.group(2)}f'|format({m.group(1)}))", expr)

    if is_unsupported_expr(expr):
        warnings.append(original)
        return "art_expr(" + py_string(original) + ")"
    return expr


def split_top_level_ternary(expr: str) -> tuple[str, str, str] | None:
    depth = 0
    quote = ""
    qpos = -1
    for i, ch in enumerate(expr):
        if quote:
            if ch == quote and (i == 0 or expr[i - 1] != "\\"):
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            continue
        if ch in "([{" :
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if ch == "?" and depth == 0:
            qpos = i
            break
    if qpos < 0:
        return None
    depth = 0
    quote = ""
    for i in range(qpos + 1, len(expr)):
        ch = expr[i]
        if quote:
            if ch == quote and expr[i - 1] != "\\":
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            continue
        if ch in "([{" :
            depth += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            continue
        if ch == ":" and depth == 0:
            return expr[:qpos].strip(), expr[qpos + 1:i].strip(), expr[i + 1:].strip()
    return None


def is_unsupported_expr(expr: str) -> bool:
    if any(marker in expr for marker in ART_ONLY_MARKERS):
        return True
    if ".replace(/" in expr:
        return True
    if "=>" in expr:
        return True
    if "?" in expr:
        return True
    if "@" in expr:
        return True
    return False


def py_string(value: str) -> str:
    return repr(value)


def write_doc(converted: list[dict[str, str]], warnings: dict[str, list[str]]) -> None:
    folders = sorted([p for p in SOURCE_ROOT.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    converted_by_folder: dict[str, list[dict[str, str]]] = {}
    for item in converted:
        converted_by_folder.setdefault(item["folder"], []).append(item)

    lines: list[str] = []
    lines.append("# Jinja2 Template Migration Inventory")
    lines.append("")
    lines.append("This document tracks the static template migration from upstream `phi-plugin/resources/html` into `D:\\astrbot_plugin_phi_plugin\\jinja2`.")
    lines.append("")
    lines.append("Rules for this pass:")
    lines.append("")
    lines.append("- Keep the upstream folder names one-to-one under the Jinja2 template root.")
    lines.append("- Convert every `.art` file into a same-name `.html` file.")
    lines.append("- Keep CSS and binary assets listed here, but do not duplicate them into the Jinja2 directory in this pass.")
    lines.append("- Rows marked `Converted` have a generated Jinja2-syntax `.html` file. Rows with review notes may still need manual expression parity checks before runtime use.")
    lines.append("")
    lines.append("## Folder Mapping")
    lines.append("")
    lines.append("| Upstream folder | Jinja2 folder | ART files | CSS files | Status | Confirmation |")
    lines.append("|---|---|---|---|---|---|")
    for folder in folders:
        rel = folder.relative_to(SOURCE_ROOT).as_posix()
        arts = sorted(p.name for p in folder.glob("*.art"))
        css = sorted(p.name for p in folder.glob("*.css"))
        if arts:
            status = "Converted"
            confirmation = "; ".join(f"`{Path(name).with_suffix('.html').name}` written" for name in arts)
        else:
            status = "Resource only"
            confirmation = "No `.art` templates to convert"
        lines.append(
            "| "
            + f"`{rel}` | `D:\\astrbot_plugin_phi_plugin\\jinja2\\{rel}` | {fmt_list(arts)} | {fmt_list(css)} | {status} | {confirmation} |"
        )
    lines.append("")
    lines.append("## Converted Template Files")
    lines.append("")
    lines.append("| Source `.art` | Target `.html` | Status | Review notes |")
    lines.append("|---|---|---|---|")
    for item in converted:
        source = item["source"]
        note_count = int(item["warnings"])
        status = "Converted" if note_count == 0 else "Converted, needs expression review"
        note = "None" if note_count == 0 else f"{note_count} art-template/JS expression(s) wrapped with `art_expr(...)` or simplified; inspect before runtime rendering."
        lines.append(f"| `{source}` | `D:\\astrbot_plugin_phi_plugin\\jinja2\\{item['target']}` | {status} | {note} |")
    if warnings:
        lines.append("")
        lines.append("## Expression Review Queue")
        lines.append("")
        lines.append("These expressions were not safely reducible to plain Jinja2 in the automatic pass.")
        lines.append("")
        for source, items in warnings.items():
            unique = []
            seen = set()
            for expr in items:
                if expr not in seen:
                    seen.add(expr)
                    unique.append(expr)
            lines.append(f"### `{source}`")
            lines.append("")
            for expr in unique[:50]:
                lines.append(f"- `{expr.replace('`', '\\`')}`")
            if len(unique) > 50:
                lines.append(f"- ... {len(unique) - 50} more")
            lines.append("")
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def fmt_list(values: Iterable[str]) -> str:
    values = list(values)
    if not values:
        return "-"
    return ", ".join(f"`{value}`" for value in values)


if __name__ == "__main__":
    main()
