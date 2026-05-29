from __future__ import annotations

from pathlib import Path

from ..models import Best30Result, ScoreRecord, SearchHit, Song, UserSummary

HELP_TEXT = """
Phi Plugin Query Core

可用命令：
phi help - 查看帮助
phi song <曲名/别名> - 查询曲目信息
phi search <关键词> - 搜索曲目
phi rand - 随机曲目
phi ill <曲名/别名> - 发送本地曲绘
phi bind <sessionToken|查询ID> - 绑定 Phigros token 或查询平台 ID
phi auth <API Token> - 使用查询平台 API Token 登录并保存 sessionToken
phi unbind - 解绑并清理缓存
phi clean - 清理当前用户数据
phi update - 拉取并缓存存档
phi b30 / phi rks / phi pgr - 查询 B30/RKS
phi score <曲名/别名> - 查询单曲成绩
phi info - 查询个人统计
phi data - 查询 Data 数量
phi id - 查看当前绑定的查询 ID / PlayerId
phi sessiontoken - 查看当前绑定 token 的脱敏信息

暂未迁移：小游戏、签到任务、排行榜、评论、谱面标签、管理命令、Puppeteer 图片模板。
""".strip()


def render_help() -> str:
    return HELP_TEXT


def render_song(song: Song) -> str:
    lines = [f"{song.title}", f"ID: {song.id}"]
    if song.composer:
        lines.append(f"曲师: {song.composer}")
    if song.illustrator:
        lines.append(f"画师: {song.illustrator}")
    if song.bpm:
        lines.append(f"BPM: {song.bpm}")
    if song.length:
        lines.append(f"时长: {song.length}")
    if song.chapter:
        lines.append(f"章节: {song.chapter}")
    charts = []
    for chart in song.display_charts():
        diff = chart.difficulty_text or ("?" if chart.difficulty is None else f"{chart.difficulty:.1f}")
        suffix = f" ({chart.combo} notes)" if chart.combo else ""
        charts.append(f"{chart.rank} {diff}{suffix}")
    if charts:
        lines.append("难度: " + " / ".join(charts))
    if song.aliases:
        lines.append("别名: " + "、".join(song.aliases[:8]))
    if song.sp_info:
        lines.append("特殊信息: " + song.sp_info.splitlines()[0])
    return "\n".join(lines)


def render_search(query: str, hits: list[SearchHit]) -> str:
    if not hits:
        return f"未找到与「{query}」相关的曲目。"
    lines = [f"搜索「{query}」结果："]
    for index, hit in enumerate(hits, 1):
        lines.append(f"{index}. {hit.song.title} ({hit.song.id}) - 匹配: {hit.matched}")
    return "\n".join(lines)


def render_random(song: Song) -> str:
    return "随机曲目：\n" + render_song(song)


def render_missing_illustration(song: Song) -> str:
    return f"暂未找到「{song.title}」的本地曲绘。可以之后补充 original_ill 资源目录。"


def render_need_query(command: str) -> str:
    return f"请在命令后添加查询内容，例如：phi {command} Glaciaxion"


def render_not_bound() -> str:
    return "你还没有绑定 sessionToken 或查询 ID。请使用 phi bind <sessionToken|查询ID> 后再 phi update。"


def render_no_cached_save() -> str:
    return "还没有可用的本地存档缓存。请先使用 phi update。"


def render_bind_ok(api_id: str | None = None, warning: str = "") -> str:
    lines = ["绑定成功。接下来可以使用 phi update 拉取存档。"]
    if api_id:
        lines.append(f"查询 ID: {api_id}")
    if warning:
        lines.append(f"提示: {warning}")
    return "\n".join(lines)


def render_bind_need_account() -> str:
    return (
        "请提供 sessionToken 或查询 ID。\n"
        "格式：phi bind <sessionToken|查询ID>\n"
        "扫码登录 qrcode 流程还在迁移中，本轮先支持 token/API ID 绑定。"
    )


def render_qrcode_not_available() -> str:
    return "TapTap 扫码登录流程还未迁移完成。当前请先使用 phi bind <sessionToken> 或 phi bind <查询ID>。"


def render_auth_need_token() -> str:
    return (
        "请提供查询平台 API Token。\n"
        "格式：phi auth <API Token>\n"
        "登录成功后会保存 sessionToken，但不会在聊天中明文展示。"
    )


def render_auth_ok(api_id: str | None = None) -> str:
    lines = ["登录成功，sessionToken 已保存。接下来可以使用 phi update 拉取存档。"]
    if api_id:
        lines.append(f"查询 ID: {api_id}")
    lines.append("出于安全原因，本插件不会在聊天中明文输出完整 token。")
    return "\n".join(lines)


def render_unbind(ok: bool) -> str:
    return "已解绑并清理缓存。" if ok else "当前没有绑定数据。"


def render_id_info(api_id: str | None, player_id: str = "", player_name: str = "") -> str:
    if not api_id and not player_id:
        return "还没有可用的 ID 信息。请先使用 phi bind <sessionToken|查询ID>，必要时再运行 phi update。"
    lines = ["当前绑定信息："]
    lines.append(f"查询 ID: {api_id or '未绑定'}")
    if player_id:
        lines.append(f"PlayerId: {player_id}")
    if player_name and player_name != player_id:
        lines.append(f"玩家名: {player_name}")
    return "\n".join(lines)


def render_session_token(token: str | None, api_id: str | None = None) -> str:
    if not token:
        return "当前没有本地 sessionToken。若已绑定查询 ID，可以继续使用 phi update。"
    masked = token[:4] + "*" * 17 + token[-4:]
    lines = [
        "当前本地 sessionToken（已脱敏）：",
        masked,
        "出于安全原因，AstrBot 版不会在聊天中明文输出完整 token。",
    ]
    if api_id:
        lines.append(f"查询 ID: {api_id}")
    return "\n".join(lines)


def render_update_ok(summary: UserSummary) -> str:
    return (
        "存档更新完成。\n"
        f"玩家: {summary.player_name or summary.player_id or '未知'}\n"
        f"RKS: {summary.ranking_score:.4f}\n"
        f"成绩记录: {summary.total_records}"
    )


def render_update_failed(message: str) -> str:
    return "更新存档失败：" + message


def render_data(money: list[int]) -> str:
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    parts = [f"{value}{unit}" for value, unit in reversed(list(zip(money, units))) if value]
    return "你的 Data 数量为：" + (" ".join(parts) if parts else "0KiB")


def render_missing_data() -> str:
    return "缓存存档中没有 Data 信息。请先使用 phi update 获取包含 gameProgress 的存档。"


def render_b30(result: Best30Result, limit: int = 30) -> str:
    lines = [
        f"官方 RKS: {result.official_rks:.4f}",
        f"计算 B30: {result.computed_rks:.4f}",
        f"记录数: {result.total_records}",
        "",
        "Best 30:",
    ]
    for index, record in enumerate(result.records[:limit], 1):
        lines.append(_record_line(index, record))
    return "\n".join(lines)


def render_score(song: Song, records: list[ScoreRecord]) -> str:
    if not records:
        return f"缓存存档中没有「{song.title}」的成绩。"
    lines = [f"{song.title} 成绩："]
    for index, record in enumerate(records, 1):
        lines.append(_record_line(index, record, include_song=False))
    return "\n".join(lines)


def render_user_info(summary: UserSummary) -> str:
    return "\n".join([
        "玩家信息：",
        f"昵称: {summary.player_name or '未知'}",
        f"Player ID: {summary.player_id or '未知'}",
        f"RKS: {summary.ranking_score:.4f}",
        f"课题分: {summary.challenge_mode_rank if summary.challenge_mode_rank is not None else '未知'}",
        f"游戏版本: {summary.game_version if summary.game_version is not None else '未知'}",
        f"成绩记录: {summary.total_records}",
        f"Phi: {summary.phi_count}",
        f"FC: {summary.fc_count}",
    ])


def render_unsupported(name: str) -> str:
    return f"{name} 暂未在 AstrBot 查询核心版中迁移。当前先支持 help/song/search/rand/ill/bind/auth/update/b30/score/info/id/sessiontoken。"


def _record_line(index: int, record: ScoreRecord, include_song: bool = True) -> str:
    song = f" {record.song_title}" if include_song else ""
    fc = " FC" if record.fc else ""
    return (
        f"{index}. {record.rank}{song} "
        f"{record.score:,} / {record.acc:.4f}% / "
        f"定数 {record.difficulty:.1f} / RKS {record.rks:.4f} / {record.rating}{fc}"
    )
