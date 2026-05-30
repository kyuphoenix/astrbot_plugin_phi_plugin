from __future__ import annotations

from ._b30_common import render_best30
from .common import CommandContext, CommandResult

ALIASES = {"arcgros", "arcgrosb19"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    result = await render_best30(ctx, user_id)
    if result.kind == "text" and result.value.startswith("官方 RKS"):
        result.value = "Arcgros 风格查分（文本等价版）\n" + result.value
    return result
