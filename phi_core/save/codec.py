from __future__ import annotations

from typing import Any

from ..models import SaveSnapshot


class SaveNotAvailable(RuntimeError):
    pass


def normalize_save(user_id: str, token: str, data: dict[str, Any]) -> SaveSnapshot:
    if not isinstance(data, dict):
        raise SaveNotAvailable("服务返回的存档不是 JSON 对象。")

    save_info = data.get("saveInfo")
    game_record = data.get("gameRecord")
    if not isinstance(save_info, dict) or not isinstance(game_record, dict):
        raise SaveNotAvailable("服务没有返回标准化存档。当前版本还不能直接解析原始加密云存档。")

    summary = save_info.get("summary") if isinstance(save_info.get("summary"), dict) else {}
    game_user = data.get("gameuser") if isinstance(data.get("gameuser"), dict) else {}

    player_id = _first_text(save_info.get("PlayerId"), save_info.get("playerId"), game_user.get("id"))

    return SaveSnapshot(
        user_id=str(user_id),
        session_token=str(data.get("session") or token or ""),
        player_id=player_id,
        player_name=_display_player_name(save_info, game_user, player_id),
        ranking_score=_as_float(summary.get("rankingScore")),
        challenge_mode_rank=summary.get("challengeModeRank"),
        game_version=summary.get("gameVersion"),
        raw=data,
    )


def snapshot_to_json(snapshot: SaveSnapshot) -> dict[str, Any]:
    raw = dict(snapshot.raw)
    raw.setdefault("session", snapshot.session_token)
    return raw


def _display_player_name(save_info: dict[str, Any], game_user: dict[str, Any], fallback: str = "") -> str:
    for value in (save_info.get("PlayerId"), save_info.get("nickname"), game_user.get("PlayerId"), game_user.get("name"), fallback):
        text = _first_text(value)
        if text and text.casefold() not in {"user", "unknown", "none", "null"}:
            return text
    return fallback


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
