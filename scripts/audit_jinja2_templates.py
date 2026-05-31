from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SOURCE_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\phi-plugin\resources\html")
TARGET_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\jinja2")

ART_TOKEN_RE = re.compile(r"{{\s*(.*?)\s*}}", re.S)
JINJA_VAR_RE = re.compile(r"{{\s*(.*?)\s*}}", re.S)
JINJA_STMT_RE = re.compile(r"{%\s*(.*?)\s*%}", re.S)
JINJA_COMMENT_RE = re.compile(r"{#.*?#}", re.S)
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.I | re.S)
ART_EXPR_RE = re.compile(r"art_expr\((?:'[^'\\]*(?:\\.[^'\\]*)*'|\"[^\"\\]*(?:\\.[^\"\\]*)*\")\)", re.S)
RESOURCE_RE = re.compile(r"html/[A-Za-z0-9_./\-\u4e00-\u9fff\[\] ()!+,&]+?\.(?:css|js|png|jpg|jpeg|webp|ttf|TTF)")
LEFTOVER_PATTERNS = [
    "{{if",
    "{{each",
    "{{extend",
    "{{block",
    "{{/",
    ".toFixed(",
    "?.",
    "||",
    "&&",
    "Math.",
    "fCompute.",
    "<%",
]

CONTROL_OVERRIDES = {
    # The first upstream `each rating` loop only mutates `maxv` via raw JS.
    # Jinja2 templates cannot mutate outer-scope values that way reliably, so
    # the migrated template expects the data adapter to provide `rating_max`.
    "lvsco/lvsco.art": {"if": -1, "each": -1},
    # Raw `<% for (...) %>` over `e.list` is converted into a real Jinja2 loop.
    "rankingList/rankingList.art": {"each": 1},
    # Jinja2-safe row rendering adds small guards for optional composer/rating
    # strings after removing generated JavaScript template-string leftovers.
    "list/list.art": {"if": 1},
    "suggest/suggest.art": {"if": 7},
}

RESOURCE_OVERRIDES = {
    "rankingList-old/rankingList.art": {
        "html/rankingList/rankingList.css": "html/rankingList-old/rankingList.css",
    },
}


@dataclass
class AuditResult:
    folder: str
    source: str
    target: str
    exists: bool
    literal_score: float
    literal_missing: int
    art_counts: dict[str, int]
    jinja_counts: dict[str, int]
    missing_resources: list[str]
    extra_resources: list[str]
    art_expr_count: int
    leftovers: list[str]
    status: str


def main() -> None:
    results = [audit_file(path) for path in sorted(SOURCE_ROOT.rglob("*.art"), key=lambda p: p.relative_to(SOURCE_ROOT).as_posix().lower())]
    failed = [item for item in results if item.status == "Fail"]
    warn = [item for item in results if item.status == "Review"]
    print(f"audited {len(results)} templates")
    print(f"pass={len(results) - len(failed) - len(warn)} review={len(warn)} fail={len(failed)}")
    print("details: use docs/jinja2-migration-list.md as the migration tracker")
    if failed:
        for item in failed:
            print(f"FAIL {item.source}: literal_score={item.literal_score:.3f} missing_resources={item.missing_resources} leftovers={item.leftovers}")
        raise SystemExit(1)


def audit_file(art_path: Path) -> AuditResult:
    rel = art_path.relative_to(SOURCE_ROOT)
    target = TARGET_ROOT / rel.with_suffix(".html")
    source_text = art_path.read_text(encoding="utf-8-sig")
    target_text = target.read_text(encoding="utf-8") if target.exists() else ""
    source_name = rel.as_posix()
    for old_resource, new_resource in RESOURCE_OVERRIDES.get(source_name, {}).items():
        source_text = source_text.replace(old_resource, new_resource)
    art_counts = art_control_counts(source_text)
    jinja_counts = jinja_control_counts(target_text)
    literal_score, literal_missing = literal_parity(source_text, target_text)
    source_resources = sorted(set(RESOURCE_RE.findall(source_text.replace("{{_res_path}}", ""))))
    target_resources = sorted(set(RESOURCE_RE.findall(target_text)))
    resource_overrides = RESOURCE_OVERRIDES.get(source_name, {})
    expected_resources = sorted({resource_overrides.get(value, value) for value in source_resources})
    missing_resources = [value for value in expected_resources if value not in target_resources]
    extra_resources = [value for value in target_resources if value not in source_resources]
    art_expr_count = target_text.count("art_expr(")
    leftovers = raw_leftovers(target_text)
    status = classify(rel.as_posix(), target.exists(), literal_score, literal_missing, art_counts, jinja_counts, missing_resources, leftovers)
    return AuditResult(
        folder=rel.parts[0],
        source=rel.as_posix(),
        target=str(target),
        exists=target.exists(),
        literal_score=literal_score,
        literal_missing=literal_missing,
        art_counts=art_counts,
        jinja_counts=jinja_counts,
        missing_resources=missing_resources,
        extra_resources=extra_resources,
        art_expr_count=art_expr_count,
        leftovers=leftovers,
        status=status,
    )


def classify(
    source: str,
    exists: bool,
    literal_score: float,
    literal_missing: int,
    art_counts: dict[str, int],
    jinja_counts: dict[str, int],
    missing_resources: list[str],
    leftovers: list[str],
) -> str:
    if not exists:
        return "Fail"
    if literal_score < 0.985 or literal_missing > 0:
        return "Fail"
    if missing_resources:
        return "Fail"
    if leftovers:
        return "Review"
    control_override = CONTROL_OVERRIDES.get(source, {})
    if art_counts.get("each", 0) + control_override.get("each", 0) != jinja_counts.get("for", 0):
        return "Fail"
    if art_counts.get("block", 0) != jinja_counts.get("block", 0):
        return "Fail"
    if art_counts.get("extend", 0) != jinja_counts.get("extends", 0):
        return "Fail"
    # Jinja has one `if` tag for each art `if`, plus one for every converted `else if` as `elif`.
    if art_counts.get("if", 0) + control_override.get("if", 0) != jinja_counts.get("if", 0):
        return "Fail"
    if art_counts.get("else_if", 0) != jinja_counts.get("elif", 0):
        return "Fail"
    return "Review" if literal_score < 1.0 else "Pass"


def raw_leftovers(text: str) -> list[str]:
    # Keep real generated template syntax clean, but do not flag intentional
    # art_expr review markers or JavaScript code inside the original templates.
    cleaned = SCRIPT_RE.sub("", text)
    cleaned = ART_EXPR_RE.sub("art_expr('...')", cleaned)
    return [pattern for pattern in LEFTOVER_PATTERNS if pattern in cleaned]


def art_control_counts(text: str) -> dict[str, int]:
    counts = {"extend": 0, "block": 0, "if": 0, "else_if": 0, "else": 0, "each": 0}
    for raw in ART_TOKEN_RE.findall(text):
        token = raw.strip()
        if token.startswith("extend "):
            counts["extend"] += 1
        elif token.startswith("block "):
            counts["block"] += 1
        elif token.startswith("if "):
            counts["if"] += 1
        elif token.startswith("else if "):
            counts["else_if"] += 1
        elif token == "else":
            counts["else"] += 1
        elif token.startswith("each "):
            counts["each"] += 1
    return counts


def jinja_control_counts(text: str) -> dict[str, int]:
    counts = {"extends": 0, "block": 0, "if": 0, "elif": 0, "else": 0, "for": 0}
    for raw in JINJA_STMT_RE.findall(text):
        token = raw.strip()
        if token.startswith("extends "):
            counts["extends"] += 1
        elif token.startswith("block "):
            counts["block"] += 1
        elif token.startswith("if "):
            counts["if"] += 1
        elif token.startswith("elif "):
            counts["elif"] += 1
        elif token == "else":
            counts["else"] += 1
        elif token.startswith("for "):
            counts["for"] += 1
    return counts


def literal_parity(source: str, target: str) -> tuple[float, int]:
    source_chunks = literal_chunks_from_art(source)
    target_normalized = normalize_literal_text(literal_text_from_jinja(target))
    missing = [chunk for chunk in source_chunks if chunk and chunk not in target_normalized]
    if not source_chunks:
        return 1.0, 0
    return (len(source_chunks) - len(missing)) / len(source_chunks), len(missing)


def literal_chunks_from_art(text: str) -> list[str]:
    text = re.sub(r"<%.*?%>", "", text, flags=re.S)
    stripped = ART_TOKEN_RE.sub("", text)
    chunks = [normalize_literal_text(chunk) for chunk in re.split(r"\n\s*\n", stripped)]
    return [chunk for chunk in chunks if len(chunk) >= 12]


def literal_text_from_jinja(text: str) -> str:
    text = JINJA_COMMENT_RE.sub("", text)
    text = JINJA_STMT_RE.sub("", text)
    text = JINJA_VAR_RE.sub("", text)
    return text


def normalize_literal_text(text: str) -> str:
    text = text.replace("{{_res_path}}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def control_summary(item: AuditResult) -> str:
    pairs = [
        ("extend", item.art_counts.get("extend", 0), item.jinja_counts.get("extends", 0)),
        ("block", item.art_counts.get("block", 0), item.jinja_counts.get("block", 0)),
        ("if", item.art_counts.get("if", 0), item.jinja_counts.get("if", 0)),
        ("elif", item.art_counts.get("else_if", 0), item.jinja_counts.get("elif", 0)),
        ("each/for", item.art_counts.get("each", 0), item.jinja_counts.get("for", 0)),
    ]
    return ", ".join(f"{name} {left}/{right}" for name, left, right in pairs)


if __name__ == "__main__":
    main()
