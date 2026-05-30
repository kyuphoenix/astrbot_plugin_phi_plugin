from __future__ import annotations

import random
from datetime import datetime

from ._notes import (
    apply_task_rewards,
    build_sign_panel_data,
    day_start,
    hello_message,
    load_notes,
    maybe_refresh_daily_tasks,
    parse_datetime,
    save_notes,
    today_key,
)
from ._rendering import render_original_html
from .common import CommandContext, CommandResult
from ..render import original

ALIASES = {"sign", "signin", "sign in", "签到", "打卡"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    now = datetime.now()
    notes = load_notes(ctx, user_id)
    snapshot = ctx.load_snapshot(user_id)
    apply_task_rewards(ctx, user_id, snapshot, notes)

    signed_now = False
    reward = 0
    last_sign = parse_datetime(notes.get("sign_in"))
    key = today_key(now)
    if last_sign is None or last_sign < day_start(now):
        signed_now = True
        reward = _daily_reward(now)
        notes["money"] = int(notes.get("money") or 0) + reward
        notes["sign_in"] = now.isoformat()
        history = notes.get("sign_history") if isinstance(notes.get("sign_history"), list) else []
        if key not in history:
            history.append(key)
        notes["sign_history"] = history
        save_notes(ctx, user_id, notes)
    else:
        history = notes.get("sign_history") if isinstance(notes.get("sign_history"), list) else []
        if key not in history:
            history.append(key)
            notes["sign_history"] = history
            save_notes(ctx, user_id, notes)

    await maybe_refresh_daily_tasks(ctx, user_id, snapshot, notes)
    data = build_sign_panel_data(ctx, user_id, snapshot, notes)
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        image = CommandResult.image(await render_original_html(ctx, original.sign_html(ctx.paths, data), "sign"))
        text = _signed_text(notes, reward) if signed_now else _already_signed_text(notes, last_sign or now)
        if ctx.sender is not None:
            await ctx.sender(image)
            return CommandResult.text(text)
        return image
    if signed_now:
        return CommandResult.text(_signed_text(notes, reward))
    return CommandResult.text(_already_signed_text(notes, last_sign or now))


def _daily_reward(now: datetime) -> int:
    if now.month == 4 and now.day == 1:
        return 41
    return random.randint(5, 20)


def _signed_text(notes: dict, reward: int) -> str:
    return f"签到成功！{hello_message()}\n恭喜你获得了 {reward} Note！当前 Note：{notes.get('money', 0)}"


def _already_signed_text(notes: dict, last_sign: datetime) -> str:
    return f"你在今天 {last_sign.strftime('%H:%M:%S')} 的时候已经签过到了哦。\n你现在的 Note 数量：{notes.get('money', 0)}"
