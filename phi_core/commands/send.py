from __future__ import annotations

import math

from ._notes import load_notes, parse_transfer_args, save_notes
from .common import CommandContext, CommandResult

ALIASES = {"send", "送", "转"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    parsed = parse_transfer_args(args)
    if parsed is None:
        return CommandResult.text("格式错误，请使用：phi send <QQ号或@> <数量>")
    target, amount = parsed
    if amount <= 0 or not math.isfinite(amount):
        return CommandResult.text("你看看你输入的是正常数字嘛。")

    sender_notes = load_notes(ctx, user_id)
    if target == str(user_id):
        if int(sender_notes.get("money") or 0) >= 20:
            sender_notes["money"] = int(sender_notes.get("money") or 0) - 20
            save_notes(ctx, user_id, sender_notes)
            return CommandResult.text("转账成功...吗？目标是你自己。\n转账失败！扣除 20 Notes。")
        return CommandResult.text("转账成功...吗？目标是你自己。\n但你连 20 Notes 都没有，这次就不扣啦。")

    if int(sender_notes.get("money") or 0) < amount:
        return CommandResult.text(f"你当前的 Note 数量不够哦！\n当前 Note：{sender_notes.get('money', 0)}")

    target_notes = load_notes(ctx, target)
    sender_old = int(sender_notes.get("money") or 0)
    target_old = int(target_notes.get("money") or 0)
    received = math.ceil(amount * 0.8)
    sender_notes["money"] = sender_old - amount
    target_notes["money"] = target_old + received
    save_notes(ctx, user_id, sender_notes)
    save_notes(ctx, target, target_notes)
    return CommandResult.text(
        "转账成功！\n"
        f"你的 Note：{sender_old} - {amount} = {sender_notes['money']}\n"
        f"{target} 的 Note：{target_old} + {received} = {target_notes['money']}"
    )
