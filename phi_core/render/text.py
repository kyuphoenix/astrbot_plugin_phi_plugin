from __future__ import annotations

from pathlib import Path

from ..data.resources import VersionLog
from ..models import (
    Best30Result,
    ChartEntry,
    LevelScoreSummary,
    ProgressScoreChange,
    ScoreListEntry,
    ScoreRecord,
    SearchHit,
    Song,
    SuggestEntry,
    UpdateProgressSummary,
    UserSummary,
)
from ..query.history import AchievementRow, ChapterSummary, HistoryB30Change, HistorySummary

HELP_TEXT = """
Phi Plugin Query Core

可用命令：
phi help - 查看帮助
phi song <曲名/别名> - 查询曲目信息
phi search <关键词> - 搜索曲目
phi rand - 随机曲目
phi ill <曲名/别名> - 发送本地曲绘
phi down ill - 下载或更新原版曲绘资源
phi bind <sessionToken|查询ID|qrcode> - 绑定 Phigros token、查询平台 ID 或 TapTap 扫码登录
phi auth <API Token> - 使用查询平台 API Token 登录并保存 sessionToken
phi unbind - 解绑并清理缓存
phi clean - 清理当前用户数据
phi update - 更新存档并查看进步情况
phi b30 / phi rks / phi pgr - 查询 B30/RKS
phi score <曲名/别名> - 查询单曲成绩
phi info - 查询个人统计
phi data - 查询 Data 数量
phi id - 查看当前绑定的查询 ID / PlayerId
phi sessiontoken - 查看当前绑定 token 的脱敏信息
phi tips - 随机 Tips
phi alias <曲名/别名> - 查询曲目别名
phi com <定数> <acc> - 计算等效 RKS
phi table <定数> - 查询定数表
phi best [数量] - 文本版 Best 列表
phi p30/fc30/x30 - AP/FC/1 Good 模式成绩列表
phi list [条件] - 按定数/ACC/评级筛选成绩
phi lvscore [条件] - 统计指定范围成绩
phi lmtacc <acc> - 查看 ACC 下限后的 Best 列表
phi suggest - 推分建议
phi randclg [范围] - 随机三曲课题
phi chap <章节|all> - 查询章节成绩概览
phi achievement <定数整数> - 查询某一整档定数成就
phi hisb30 - 查看历史 B30 进出记录
phi 2025history - 查看历史年度总结
phi setnick 原名 ---> 别名 - 管理员添加本地别名
phi live - 查询直播速递
phi cmt <曲名> / <曲名> <难度> 换行 <内容> - 查看或发表在线评论
phi mycmt / recmt <ID> - 查看或删除自己的在线评论
phi addtag <曲名> <难度> [标签...] - 查看或提交谱面标签
phi newlog - 查看本地曲库更新日志
phi newnotice - 查看本地公告

暂未迁移：小游戏、排行榜、管理命令、完整原版图片模板。
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
    lines = ["绑定成功。正在尝试自动同步玩家数据，成功后可直接使用 phi pgr。"]
    if api_id:
        lines.append(f"查询 ID: {api_id}")
    if warning:
        lines.append(f"提示: {warning}")
    return "\n".join(lines)


def render_bind_need_account() -> str:
    return (
        "请提供 sessionToken 或查询 ID。\n"
        "格式：phi bind <sessionToken|查询ID>\n"
        "扫码登录：phi bind qrcode"
    )


def render_qrcode_not_available() -> str:
    return "TapTap 扫码登录组件未初始化。当前请先使用 phi bind <sessionToken> 或 phi bind <查询ID>。"


def render_auth_need_token() -> str:
    return (
        "请提供查询平台 API Token。\n"
        "格式：phi auth <API Token>\n"
        "登录成功后会保存 sessionToken，但不会在聊天中明文展示。"
    )


def render_auth_ok(api_id: str | None = None) -> str:
    lines = ["登录成功，sessionToken 已保存。正在尝试自动同步玩家数据。"]
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


def render_auto_sync_ok(summary: UserSummary) -> str:
    player = summary.player_name or summary.player_id or "未知"
    return (
        "自动同步玩家数据完成。\n"
        f"玩家: {player}\n"
        f"RKS: {summary.ranking_score:.4f}\n"
        f"成绩记录: {summary.total_records}\n"
        "现在可以直接使用 phi pgr / phi b30。"
    )


def render_auto_sync_failed(message: str) -> str:
    return (
        "自动同步玩家数据失败，绑定信息已保存。\n"
        "稍后可以使用 phi update 重试。\n"
        f"错误信息: {message}"
    )


def render_update_progress(summary: UpdateProgressSummary) -> str:
    player = summary.player_name or summary.player_id or "未知"
    lines = [
        "存档更新完成，进步摘要：",
        f"玩家: {player}",
        f"存档时间: {summary.modified_at}",
        f"RKS: {summary.ranking_score:.4f}{_format_float_delta(summary.rks_delta, digits=4)}",
        f"成绩记录: {summary.total_records}",
    ]
    if summary.challenge_mode_rank is not None:
        lines.append(f"课题分: {summary.challenge_mode_rank}{_format_number_delta(summary.challenge_delta)}")
    if summary.data_money is not None:
        lines.append(f"Data: {_format_money(summary.data_money)}{_format_data_delta(summary.data_delta)}")

    if summary.current_update_count:
        prefix = "首次记录" if summary.is_first_record else "当前存档时间记录"
        lines.append(f"{prefix}: {summary.current_update_count} 份成绩")
    else:
        lines.append("未收集到新的成绩变化。")

    if summary.recent_days:
        lines.extend(["", "近期成绩变化："])
        for day in summary.recent_days:
            lines.append(f"[{day.date}] 共 {day.update_count} 份")
            for change in day.changes:
                lines.append(_progress_change_line(change))
    else:
        lines.extend(["", "近期成绩变化：暂无本地历史记录。"])

    if summary.player_id:
        lines.append(f"\nPlayerId: {summary.player_id}")
    return "\n".join(lines)


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


def render_records(title: str, records: list[ScoreRecord], *, official_rks: float = 0.0, average_rks: float | None = None) -> str:
    if not records:
        return f"{title}\n没有找到符合条件的成绩。"
    lines = [title]
    if official_rks:
        lines.append(f"官方 RKS: {official_rks:.4f}")
    if average_rks is not None:
        lines.append(f"列表均值 RKS: {average_rks:.4f}")
    lines.append("")
    for index, record in enumerate(records, 1):
        lines.append(_record_line(index, record))
    return "\n".join(lines)


def render_score(song: Song, records: list[ScoreRecord]) -> str:
    if not records:
        return f"缓存存档中没有「{song.title}」的成绩。"
    lines = [f"{song.title} 成绩："]
    for index, record in enumerate(records, 1):
        lines.append(_record_line(index, record, include_song=False))
    return "\n".join(lines)


def render_alias(song: Song) -> str:
    lines = [f"name: {song.title}", f"id: {song.id}"]
    if song.aliases:
        lines.append("已有别名：")
        lines.extend(f"- {alias}" for alias in song.aliases)
    else:
        lines.append("本地别名库里还没有这首歌的别名。")
    return "\n".join(lines)


def render_com(difficulty: float, acc: float, rks: float) -> str:
    return f"定数: {difficulty:.1f}\nACC: {acc:.4f}%\n等效 RKS: {rks:.6f}"


def render_table(difficulty: float, charts: list[ChartEntry], *, version_label: str = "current", limit: int = 80) -> str:
    if not charts:
        return f"没有找到定数 {difficulty:g} 的谱面。"
    lines = [f"定数表 {difficulty:g} ({version_label})", f"共 {len(charts)} 个谱面"]
    for chart in sorted(charts, key=lambda item: (item.difficulty, item.rank, item.song_title))[:limit]:
        combo = f" / {chart.combo} notes" if chart.combo else ""
        lines.append(f"- {chart.difficulty:.1f} {chart.rank} {chart.song_title}{combo}")
    if len(charts) > limit:
        lines.append(f"... 还有 {len(charts) - limit} 个谱面未显示，请缩小范围。")
    return "\n".join(lines)


def render_score_list(entries: list[ScoreListEntry], request_lines: list[str], *, limit: int = 60) -> str:
    if not entries:
        return "没有找到符合条件的谱面或成绩。\n" + "\n".join(request_lines)
    lines = ["成绩筛选", *request_lines, f"结果: {len(entries)} 条", ""]
    for index, entry in enumerate(entries[:limit], 1):
        chart = entry.chart
        if entry.record:
            record = entry.record
            lines.append(
                f"{index}. {chart.difficulty:.1f} {chart.rank} {chart.song_title} "
                f"{record.score:,} / {record.acc:.4f}% / {record.rating.upper()} / RKS {record.rks:.4f}"
            )
        else:
            lines.append(f"{index}. {chart.difficulty:.1f} {chart.rank} {chart.song_title} NEW")
    if len(entries) > limit:
        lines.append(f"... 还有 {len(entries) - limit} 条未显示，请缩小筛选范围。")
    return "\n".join(lines)


def render_level_score(summary: LevelScoreSummary) -> str:
    return "\n".join([
        "等级成绩统计",
        f"范围: 定数 {summary.range_text} / 难度 {'/'.join(summary.levels)}",
        f"谱面数: {summary.total_charts}",
        f"已游玩: {summary.played_charts}",
        f"Phi: {summary.phi_count}",
        f"FC: {summary.fc_count}",
        f"平均 ACC: {summary.avg_acc:.4f}%",
        f"平均分: {summary.avg_score:.0f}",
        f"定数范围: {summary.lowest_difficulty:.1f}-{summary.highest_difficulty:.1f}",
        "难度分布: " + " / ".join(f"{k}:{v}" for k, v in summary.rank_counts.items() if v),
        "评级分布: " + " / ".join(f"{k}:{v}" for k, v in summary.rating_counts.items() if v),
    ])


def render_suggest(entries: list[SuggestEntry]) -> str:
    if not entries:
        return "暂时没有找到可推分建议。你可能已经很强了，或者缓存成绩太少。"
    lines = ["推分建议", "目标 ACC 为估算值，用来帮助挑歌，不等同于原插件 API 平均分建议。", ""]
    for index, item in enumerate(entries, 1):
        current = "NEW"
        if item.current:
            current = f"{item.current.acc:.4f}% / RKS {item.current.rks:.4f}"
        lines.append(
            f"{index}. {item.chart.difficulty:.1f} {item.chart.rank} {item.chart.song_title} "
            f"当前 {current} -> 目标 {item.target_acc:.4f}%"
        )
    return "\n".join(lines)


def render_random_challenge(target: int, charts: list[ChartEntry]) -> str:
    lines = [f"随机课题: {target}", ""]
    for index, chart in enumerate(charts, 1):
        lines.append(f"{index}. {chart.rank} {chart.song_title} / 定数 {chart.difficulty:.1f}")
    total = sum(int(chart.difficulty) for chart in charts)
    lines.append(f"课题值: {total}")
    return "\n".join(lines)


def render_chapter_summary(summary: ChapterSummary) -> str:
    if summary.total_charts <= 0:
        return f"章节「{summary.name}」下没有找到可统计谱面。"
    lines = [
        f"章节成绩：{summary.name}",
        f"谱面: {summary.played_charts}/{summary.total_charts}",
        "评级分布: " + " / ".join(f"{key}:{value}" for key, value in summary.rating_counts.items() if value),
        "",
        "难度进度:",
    ]
    for rank, item in summary.rank_counts.items():
        if item.total:
            lines.append(f"- {rank}: {item.played}/{item.total} / 平均 ACC {item.average_acc:.4f}%")
    if summary.top_records:
        lines.extend(["", "章节 Best:"])
        for index, record in enumerate(summary.top_records, 1):
            lines.append(_record_line(index, record))
    return "\n".join(lines)


def render_achievement(rows: list[AchievementRow], difficulty_floor: int) -> str:
    if not rows:
        return f"没有找到 {difficulty_floor}.0-{difficulty_floor}.9 的谱面。"
    lines = [f"Player Achievements {difficulty_floor}.0-{difficulty_floor}.9", ""]
    for row in rows:
        lines.append(
            f"{row.difficulty:.1f}: {row.played}/{row.total} / "
            f"最低评级 {row.min_rating.upper()} / 最低分 {row.min_score:,} / "
            f"平均 ACC {row.avg_acc:.4f}% / Phi {row.phi_count} / FC {row.fc_count}"
        )
    return "\n".join(lines)


def render_history_b30(changes: list[HistoryB30Change]) -> str:
    if not changes:
        return "还没有足够的历史记录用于分析 B30 进出变化。请先使用 phi update 积累历史。"
    lines = ["历史 B30 变化", ""]
    for change in changes:
        lines.append(f"[{change.date}]")
        for index, record in change.new_phi:
            lines.append(f"+ Phi{index}: {_record_short(record)}")
        for index, record in change.new_b27:
            lines.append(f"+ B27#{index}: {_record_short(record)}")
        for record in change.exit_phi:
            lines.append(f"- Phi: {_record_short(record)}")
        for record in change.exit_b27:
            lines.append(f"- B27: {_record_short(record)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_history_summary(summary: HistorySummary) -> str:
    lines = [
        "年度历史总结",
        f"有记录天数: {summary.total_days}",
        f"更新次数: {summary.total_updates}",
        f"历史成绩记录: {summary.total_score_records}",
        "",
        "打得最多:",
    ]
    lines.extend(_top_lines(summary.most_played))
    lines.extend([
        "",
        f"RKS 上升最多: {_format_float_pair(summary.rks_max_up, 4)}",
        f"RKS 下降最多: {_format_float_pair(summary.rks_max_down, 4)}",
        f"Data 上升最多: {_format_data_pair(summary.data_max_up)}",
        f"Data 下降最多: {_format_data_pair(summary.data_max_down)}",
        "",
        "新纪录最多:",
    ])
    lines.extend(_top_lines(summary.most_new_records))
    lines.extend(["", "AP 最多:"])
    lines.extend(_top_lines(summary.most_ap_days))
    lines.extend(["", "每天最晚推分 Top3:"])
    if summary.latest_push_times:
        lines.extend(f"- {day}: {time}" for day, time in summary.latest_push_times)
    else:
        lines.append("- 暂无")
    return "\n".join(lines)


def render_live_info(info: str) -> str:
    return "直播速递：\n" + (info.strip() if info and info.strip() else "暂无直播信息。")


def render_comments(song: Song, comments: list[dict], *, limit: int = 10) -> str:
    if not comments:
        return f"「{song.title}」暂无在线评论。"
    lines = [f"「{song.title}」评论列表："]
    for item in comments[:limit]:
        comment_id = item.get("id") or item.get("thisId") or "?"
        rank = item.get("rank") or "?"
        player = item.get("PlayerId") or item.get("playerId") or item.get("apiUserId") or "匿名"
        content = str(item.get("comment") or "").replace("\n", " ").strip()
        time = item.get("time") or item.get("createdAt") or ""
        lines.append(f"{comment_id} | {rank} | {player} | {content}" + (f" | {time}" if time else ""))
    if len(comments) > limit:
        lines.append(f"... 还有 {len(comments) - limit} 条未显示。")
    return "\n".join(lines)


def render_my_comments(comments: list[dict], *, limit: int = 20) -> str:
    if not comments:
        return "您还没有评论。"
    lines = ["您的评论列表：", "ID | 曲目 | 难度 | 内容 | 时间"]
    for item in comments[:limit]:
        comment_id = item.get("id") or item.get("thisId") or "?"
        song_id = item.get("songId") or item.get("song_id") or "?"
        rank = item.get("rank") or "?"
        content = str(item.get("comment") or "").replace("\n", " ").strip()
        time = item.get("time") or item.get("createdAt") or ""
        lines.append(f"{comment_id} | {song_id} | {rank} | {content} | {time}")
    if len(comments) > limit:
        lines.append(f"... 还有 {len(comments) - limit} 条未显示。")
    return "\n".join(lines)


def render_chart_tags(song: Song, rank: str, tags: dict[str, object]) -> str:
    if not tags:
        return f"{song.title} {rank} 暂无在线谱面标签。"
    lines = [f"{song.title} {rank} 谱面标签："]
    for tag, value in sorted(tags.items(), key=lambda item: str(item[0])):
        lines.append(f"- {tag}: {value}")
    return "\n".join(lines)


def render_tip(tip: str | None) -> str:
    return tip or "本地 tips.yaml 为空，暂时没有 Tips 可以抽。"


def render_notice(notice: dict) -> str:
    if not notice:
        return "本地 notice.json 为空或不存在。"
    lines = [str(notice.get("title") or "公告")]
    if notice.get("code") is not None:
        lines.append(f"code: {notice.get('code')}")
    content = notice.get("content")
    if isinstance(content, list):
        lines.extend(str(item) for item in content)
    elif content:
        lines.append(str(content))
    return "\n".join(lines)


def render_newlog(log: VersionLog | None, *, limit: int = 30) -> str:
    if log is None:
        return "没有找到本地版本更新日志。"
    lines = [
        f"最新版本: {log.version_label} ({log.version_code})",
        "更新信息:",
        log.whatsnew or "无文字更新说明。",
        "",
        f"谱面变更: {len(log.changes)} 条",
    ]
    for item in log.changes[:limit]:
        diffs = " / ".join(f"{rank} {item.get(rank)}" for rank in ("EZ", "HD", "IN", "AT") if item.get(rank))
        lines.append(f"- {item.get('id', 'unknown')}: {diffs}")
    if len(log.changes) > limit:
        lines.append(f"... 还有 {len(log.changes) - limit} 条未显示。")
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
    return f"{name} 暂未在 AstrBot 版中迁移。当前可用命令请查看 phi help。"


def _record_line(index: int, record: ScoreRecord, include_song: bool = True) -> str:
    song = f" {record.song_title}" if include_song else ""
    fc = " FC" if record.fc else ""
    return (
        f"{index}. {record.rank}{song} "
        f"{record.score:,} / {record.acc:.4f}% / "
        f"定数 {record.difficulty:.1f} / RKS {record.rks:.4f} / {record.rating}{fc}"
    )


def _record_short(record: ScoreRecord) -> str:
    return (
        f"{record.rank} {record.song_title} "
        f"{record.score:,} / {record.acc:.4f}% / RKS {record.rks:.4f}"
    )


def _top_lines(items: list[tuple[str, int]]) -> list[str]:
    if not items:
        return ["- 暂无"]
    return [f"- {name}: {count}" for name, count in items]


def _format_float_pair(pair: tuple[str, float] | None, digits: int) -> str:
    if pair is None:
        return "暂无"
    sign = "+" if pair[1] > 0 else ""
    return f"{pair[0]} {sign}{pair[1]:.{digits}f}"


def _format_data_pair(pair: tuple[str, int] | None) -> str:
    if pair is None:
        return "暂无"
    return f"{pair[0]} {_format_data_delta(pair[1]).strip(' ()') or '0KiB'}"


def _progress_change_line(change: ProgressScoreChange) -> str:
    score_delta = "" if change.score_old is None else f" ({_format_int_delta(change.score_new - change.score_old)})"
    acc_delta = "" if change.acc_old is None else _format_float_delta(change.acc_new - change.acc_old, digits=4, suffix="%")
    rks_delta = "" if change.rks_old is None else _format_float_delta(change.rks_new - change.rks_old, digits=4)
    fc = " FC" if change.fc_new and change.rating_new != "phi" else ""
    old_label = " NEW" if change.score_old is None else ""
    return (
        f"- {change.rank} {change.song_title}: "
        f"{change.score_new:,}{score_delta} / "
        f"{change.acc_new:.4f}%{acc_delta} / "
        f"RKS {change.rks_new:.4f}{rks_delta} / "
        f"{change.rating_new.upper()}{fc}{old_label}"
    )


def _format_float_delta(value: float | None, *, digits: int, suffix: str = "") -> str:
    if value is None or abs(value) < 10 ** (-(digits + 1)):
        return ""
    sign = "+" if value > 0 else ""
    return f" ({sign}{value:.{digits}f}{suffix})"


def _format_number_delta(value: int | float | None) -> str:
    if value is None or value == 0:
        return ""
    if isinstance(value, float) and not value.is_integer():
        sign = "+" if value > 0 else ""
        return f" ({sign}{value:.2f})"
    return f" ({_format_int_delta(int(value))})"


def _format_int_delta(value: int) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,}"


def _format_money(money: list[int]) -> str:
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    parts = [f"{value}{unit}" for value, unit in reversed(list(zip(money, units))) if value]
    return " ".join(parts) if parts else "0KiB"


def _format_data_delta(value: int | None) -> str:
    if value is None or value == 0:
        return ""
    sign = "+" if value > 0 else "-"
    amount = abs(value)
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    index = 0
    display = float(amount)
    while display >= 1024 and index < len(units) - 1:
        display /= 1024
        index += 1
    text = f"{display:.2f}".rstrip("0").rstrip(".")
    return f" ({sign}{text}{units[index]})"
