from __future__ import annotations

import re

from .common import CommandContext, CommandResult
from ..data import load_version_log, resolve_version_code
from ..query import charts_for_table
from ..render import text as render

ALIASES = {"table", "定数表"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    match = re.search(r"\d+(?:\.\d+)?", args)
    if not match:
        return CommandResult.text("请输入定数。\n格式：phi table <定数>")
    difficulty = float(match.group(0))
    version_label = "current"
    version_match = re.search(r"-v\s*(\S+)", args, flags=re.IGNORECASE)
    if version_match:
        version_code = resolve_version_code(ctx.paths.info, version_match.group(1))
        version_log = load_version_log(ctx.paths.info, version_code) if version_code is not None else None
        if version_log is None:
            return CommandResult.text(f"未找到版本 {version_match.group(1)} 的本地信息。")
        version_label = version_log.version_label
    return CommandResult.text(render.render_table(difficulty, charts_for_table(ctx.catalog, difficulty), version_label=version_label))
