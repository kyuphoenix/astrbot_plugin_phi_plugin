from __future__ import annotations

import re
from pathlib import Path

SOURCE_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\phi-plugin\resources\html")
TARGET_ROOT = Path(r"D:\astrbot_plugin_phi_plugin\jinja2")
DOC_PATH = Path("docs/jinja2-template-comparison-checklist.md")
ART_EXPR_RE = re.compile(r"art_expr\(")
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.I | re.S)
RAW_LEFTOVER_PATTERNS = ("{{if", "{{each", "{{extend", "{{block", "{{/", ".toFixed(", "?.", "||", "&&", "Math.", "fCompute.", "<%")

# These files still need human semantic parity checks before they should be used as runtime templates.
# Structural parity was verified separately by scripts/audit_jinja2_templates.py.
def raw_leftovers(text: str) -> list[str]:
    cleaned = SCRIPT_RE.sub("", text)
    cleaned = re.sub(r"art_expr\((?:'[^'\\]*(?:\\.[^'\\]*)*'|\"[^\"\\]*(?:\\.[^\"\\]*)*\")\)", "art_expr('...')", cleaned, flags=re.S)
    return [pattern for pattern in RAW_LEFTOVER_PATTERNS if pattern in cleaned]

rows = []
for art_path in sorted(SOURCE_ROOT.rglob("*.art"), key=lambda p: p.relative_to(SOURCE_ROOT).as_posix().lower()):
    rel = art_path.relative_to(SOURCE_ROOT).as_posix()
    target_rel = Path(rel).with_suffix(".html").as_posix()
    target = TARGET_ROOT / target_rel
    target_text = target.read_text(encoding="utf-8") if target.exists() else ""
    art_expr_count = target_text.count("art_expr(")
    leftovers = raw_leftovers(target_text)
    semantic_done = art_expr_count == 0 and not leftovers
    notes = []
    if art_expr_count:
        notes.append(f"{art_expr_count} art_expr")
    if leftovers:
        notes.append("raw leftovers: " + ", ".join(f"`{item}`" for item in leftovers))
    if not notes:
        notes.append("No semantic leftovers detected")
    rows.append((rel, target_rel, target.exists(), semantic_done, "; ".join(notes)))

lines = []
lines.append("# Jinja2 Template Comparison Checklist")
lines.append("")
lines.append("This checklist is the single-file tracking board for comparing upstream `.art` templates with generated Jinja2 `.html` templates.")
lines.append("")
lines.append("Use it together with:")
lines.append("")
lines.append("- `docs/jinja2-template-migration.md` for the folder inventory and generated-file list.")
lines.append("- `docs/jinja2-template-audit.md` for the latest structural audit evidence.")
lines.append("- `scripts/audit_jinja2_templates.py` for repeatable comparison checks.")
lines.append("")
lines.append("## Working Rule")
lines.append("")
lines.append("- Keep exactly one template in `In Progress` while manually reviewing or editing Jinja2 parity.")
lines.append("- Do not start another template until the current one is marked `Confirmed` or returned to `Pending` with notes.")
lines.append("- Mark `Structural Compared` only after `scripts/audit_jinja2_templates.py` reports no fail for that file.")
lines.append("- Mark `Semantic Confirmed` only after reviewing expressions, filters, conditionals, and generated output expectations against the source `.art` file.")
lines.append("- If a file contains `art_expr(...)`, it is not semantically confirmed yet, even if structural comparison passed.")
lines.append("")
lines.append("## Current Slot")
lines.append("")
lines.append("| Field | Value |")
lines.append("|---|---|")
lines.append("| Current file | None |")
lines.append("| Status | Idle |")
lines.append("| Notes | Pick one `Pending` row before editing. |")
lines.append("")
lines.append("## Checklist")
lines.append("")
lines.append("| Source `.art` | Target `.html` | Structural Compared | Semantic Confirmed | Status | Notes |")
lines.append("|---|---|---:|---:|---|---|")
for rel, target_rel, exists, semantic_done, notes in rows:
    structural = "[x]" if exists else "[ ]"
    semantic = "[x]" if semantic_done else "[ ]"
    status = "Confirmed" if semantic_done else "Pending semantic review"
    if not exists:
        status = "Missing target"
    lines.append(f"| `{rel}` | `D:\\astrbot_plugin_phi_plugin\\jinja2\\{target_rel}` | {structural} | {semantic} | {status} | {notes} |")
lines.append("")
lines.append("## Status Meaning")
lines.append("")
lines.append("- `Confirmed`: structure and obvious template semantics are clean; no `art_expr(...)` or raw template leftovers remain.")
lines.append("- `Pending semantic review`: structure exists, but expressions still need manual parity review before runtime use.")
lines.append("- `In Progress`: temporarily use this only for the one file currently being edited.")
lines.append("- `Missing target`: generated Jinja2 file is absent and must be regenerated or created manually.")
lines.append("")
lines.append("## Update Procedure")
lines.append("")
lines.append("1. Set `Current Slot` to the single file being reviewed.")
lines.append("2. Compare the source `.art` and target `.html` side by side.")
lines.append("3. Resolve `art_expr(...)` or document why it must stay as a helper call.")
lines.append("4. Run `python scripts\\audit_jinja2_templates.py`.")
lines.append("5. Mark `Semantic Confirmed` only if the file has no unresolved parity notes.")
lines.append("6. Set `Current Slot` back to `None` before moving to the next file.")

DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {DOC_PATH} with {len(rows)} template rows")
print(f"pending semantic review: {sum(1 for _,_,_,done,_ in rows if not done)}")
