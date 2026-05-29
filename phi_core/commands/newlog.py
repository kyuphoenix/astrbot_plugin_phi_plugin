from __future__ import annotations

from .common import CommandContext, CommandResult
from ..data import latest_version_log, load_version_log, resolve_version_code
from ..render import text as render

ALIASES = {"newlog"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    version = resolve_version_code(ctx.paths.info, args.strip()) if args.strip() else None
    log = load_version_log(ctx.paths.info, version) if version is not None else latest_version_log(ctx.paths.info)
    return CommandResult.text(render.render_newlog(log))
