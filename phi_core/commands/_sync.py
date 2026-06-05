from __future__ import annotations

from dataclasses import dataclass

from .common import CommandContext
from ..models import SaveSnapshot, UpdateProgressSummary, UserSummary
from ..query import merge_histories, summarize_user, update_progress_history
from ..save import SaveNotAvailable, normalize_save, snapshot_to_json


@dataclass(slots=True)
class SaveSyncResult:
    snapshot: SaveSnapshot
    previous_snapshot: SaveSnapshot | None
    summary: UserSummary
    task_reward_delta: int = 0


@dataclass(slots=True)
class ProgressSyncResult:
    snapshot: SaveSnapshot
    previous_snapshot: SaveSnapshot | None
    progress: UpdateProgressSummary
    used_remote_history: bool = False
    task_reward_delta: int = 0


async def sync_save_cache(ctx: CommandContext, user_id: str) -> SaveSyncResult:
    previous_snapshot = ctx.load_snapshot(user_id)
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    if not token and not api_id:
        raise SaveNotAvailable("请先绑定 sessionToken 或查询 ID。")

    try:
        raw = await ctx.client.fetch_cloud_save(token, user_id=user_id, api_id=api_id)
    except SaveNotAvailable:
        if not token or not api_id:
            raise
        raw = await ctx.client.fetch_cloud_save(None, user_id=user_id, api_id=api_id)

    snapshot = normalize_save(user_id, token or "", raw)
    raw_api_id = raw.get("apiId") or raw.get("api_id") or raw.get("internal_id")
    if raw_api_id and ctx.store.validate_api_id(str(raw_api_id)):
        ctx.store.set_api_id(user_id, str(raw_api_id))
    ctx.store.save_snapshot(user_id, snapshot_to_json(snapshot))
    task_reward_delta = 0
    try:
        from ._notes import apply_task_rewards, load_notes

        task_reward_delta = apply_task_rewards(ctx, user_id, snapshot, load_notes(ctx, user_id))
    except Exception:
        pass
    return SaveSyncResult(
        snapshot=snapshot,
        previous_snapshot=previous_snapshot,
        summary=summarize_user(snapshot, ctx.catalog),
        task_reward_delta=task_reward_delta,
    )


async def sync_save_with_progress(ctx: CommandContext, user_id: str) -> ProgressSyncResult:
    result = await sync_save_cache(ctx, user_id)
    token = ctx.store.get_token(user_id)
    api_id = ctx.store.get_api_id(user_id)
    history = ctx.store.load_history(user_id)
    used_remote_history = False
    if token or api_id:
        try:
            remote_history = await ctx.client.fetch_history(
                user_id,
                token=token,
                api_id=api_id,
                fields=["data", "rks", "scoreHistory", "challengeModeRank"],
            )
            history = merge_histories(remote_history, history)
            used_remote_history = True
        except SaveNotAvailable:
            pass
    updated_history, progress = update_progress_history(
        result.snapshot,
        ctx.catalog,
        history,
        previous_snapshot=result.previous_snapshot,
        max_days=ctx.config.history_score_date,
        max_per_day=ctx.config.history_day_num,
        max_total=ctx.config.history_score_num,
    )
    ctx.store.save_history(user_id, updated_history)
    if used_remote_history or token:
        try:
            await ctx.client.set_history(user_id, updated_history, token=token, api_id=api_id)
        except SaveNotAvailable:
            pass
    return ProgressSyncResult(
        snapshot=result.snapshot,
        previous_snapshot=result.previous_snapshot,
        progress=progress,
        used_remote_history=used_remote_history,
        task_reward_delta=result.task_reward_delta,
    )
