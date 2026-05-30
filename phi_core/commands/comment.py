from __future__ import annotations

from datetime import datetime
import re

from .common import CommandContext, CommandResult
from ..models import LEVELS
from ..query import find_song_scores
from ..render import text as render
from ..save import SaveNotAvailable

ALIASES = {"comment", "cmt", "评论", "评价"}


async def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    query, content = _split_comment_args(args)
    if not query:
        return CommandResult.text("请指定曲名。\n格式：phi cmt <曲名> <难度?>\\n<内容>\n查看评论：phi cmt <曲名>")

    song_query, rank = _extract_rank(query)
    song = ctx.searcher.best(song_query)
    if not song:
        return CommandResult.text(render.render_search(song_query, []))

    if not content:
        try:
            comments = await ctx.client.fetch_comments_by_song(song.id)
        except SaveNotAvailable as exc:
            return CommandResult.text(f"获取评论失败：{exc}")
        return CommandResult.text(render.render_comments(song, comments))

    token = ctx.store.get_token(user_id)
    if not token:
        return CommandResult.text("请先绑定 sessionToken 后再发表评论。")
    if len(content) > 1000:
        return CommandResult.text("评论内容不能超过 1000 字。")

    snapshot = ctx.load_snapshot(user_id)
    score = 0
    acc = 0.0
    fc = False
    if snapshot:
        records = find_song_scores(snapshot, ctx.catalog, song)
        record = next((item for item in records if item.rank == rank), None)
        if record:
            score = record.score
            acc = record.acc
            fc = record.fc

    payload = {
        "songId": song.id,
        "rank": rank,
        "rks": snapshot.ranking_score if snapshot else 0,
        "score": score,
        "acc": acc,
        "fc": fc,
        "challenge": snapshot.challenge_mode_rank if snapshot else 0,
        "time": datetime.utcnow().isoformat(),
        "comment": content,
    }
    try:
        await ctx.client.add_comment(user_id, token, payload)
    except SaveNotAvailable as exc:
        return CommandResult.text(f"在线评论失败：{exc}")
    return CommandResult.text("在线评论成功。")


def _split_comment_args(args: str) -> tuple[str, str]:
    if "\n" not in args:
        return args.strip(), ""
    query, content = args.split("\n", 1)
    return query.strip(), content.strip()


def _extract_rank(query: str) -> tuple[str, str]:
    match = re.search(r"\b(EZ|HD|IN|AT)\b", query, flags=re.IGNORECASE)
    if not match:
        return query.strip(), "IN"
    rank = match.group(1).upper()
    song_query = (query[:match.start()] + query[match.end():]).strip()
    if rank not in LEVELS:
        rank = "IN"
    return song_query, rank
