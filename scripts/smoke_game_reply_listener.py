from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, dispatch
from phi_core.commands._games import _ACTIVE_GAMES, handle_game_reply, has_active_game
from phi_core.config import PluginConfig
from phi_core.data import SongCatalog, SongSearcher
from phi_core.models import Song, SongChart
from phi_core.paths import PluginPaths
from phi_core.save import PhiApiClient, SaveStore


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 18), (20, 90, 160)).save(path)


async def main() -> None:
    tmp = ROOT / "data" / "tmp-smoke-game-listener"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    paths = PluginPaths.from_root(ROOT, tmp)
    paths.ensure_data_dir()

    titles = ["Glaciaxion", "Burn", "Igallta", "Rrharil", "Credits", "Dlyrotz", "Palescreen", "Stasis"]
    songs = {
        f"{title}.Smoke": Song(
            id=f"{title}.Smoke",
            title=title,
            composer="Smoke",
            illustrator="Tetrajectory",
            charts={"EZ": SongChart(rank="EZ", difficulty=1.0, difficulty_text="1.0", charter="Smoke", combo=100)},
        )
        for title in titles
    }
    catalog = SongCatalog(songs=songs, alias_to_id={title.casefold(): f"{title}.Smoke" for title in titles})
    for song_id in songs:
        _write_image(paths.downloaded_original_ill / "illLow" / f"{song_id}.png")

    def make_ctx(session_id: str, *, listener: bool = False) -> CommandContext:
        config = PluginConfig(render_mode="text", game_reply_listener=listener)
        return CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
            session_id=session_id,
        )

    ctx = make_ctx("group-main")
    listener_ctx = make_ctx("group-listener", listener=True)

    default_guess = await dispatch(make_ctx("hint-default-guess"), "default-guess", "guess", "")
    if "phi guess <" not in default_guess.value or "直接回复" in default_guess.value:
        raise SystemExit(f"default guess hint should keep command mode, got {default_guess!r}")

    listener_guess = await dispatch(listener_ctx, "listener-guess", "guess", "")
    if "直接回复" not in listener_guess.value or "phi guess <" not in listener_guess.value:
        raise SystemExit(f"listener guess hint should mention direct replies and command fallback, got {listener_guess!r}")
    listener_tipgame = await dispatch(make_ctx("hint-listener-tipgame", listener=True), "listener-tipgame", "tipgame", "")
    if "直接回复" not in listener_tipgame.value or "tip" not in listener_tipgame.value:
        raise SystemExit(f"listener tipgame hint should mention direct replies, got {listener_tipgame!r}")
    listener_ltr = await dispatch(make_ctx("hint-listener-ltr", listener=True), "listener-ltr", "ltr", "")
    if "直接回复 n1 <" not in listener_ltr.value or "open A" not in listener_ltr.value:
        raise SystemExit(f"listener ltr hint should mention direct replies, got {listener_ltr!r}")

    before_start = await handle_game_reply(ctx, "user-1", "Glaciaxion")
    if before_start is not None:
        raise SystemExit("listener reply should ignore users without active games")

    started = await dispatch(ctx, "user-1", "guess", "")
    if "猜曲绘" not in started.value or not has_active_game(ctx, "user-1"):
        raise SystemExit(f"guess should start active game, got {started!r}")

    wrong = await handle_game_reply(ctx, "user-1", "not glaciaxion")
    if wrong is None or "不是" not in wrong.value:
        raise SystemExit(f"listener should treat plain text as guess answer, got {wrong!r}")

    answer_title = ctx.catalog.get(_ACTIVE_GAMES[ctx.session_id].song_id).title
    right = await handle_game_reply(ctx, "user-1", answer_title)
    if right is None or "答对" not in right.value or has_active_game(ctx, "user-1"):
        raise SystemExit(f"listener should finish guess game on correct answer, got {right!r}")

    tipgame = await dispatch(ctx, "user-2", "tipgame", "")
    if "提示猜歌" not in tipgame.value:
        raise SystemExit(f"tipgame should start, got {tipgame!r}")
    tip = await handle_game_reply(ctx, "user-2", "tip")
    if tip is None or "2." not in tip.value:
        raise SystemExit(f"listener should support tip action, got {tip!r}")
    answer = await handle_game_reply(ctx, "user-2", "ans")
    if answer is None or "正确答案" not in answer.value:
        raise SystemExit(f"listener should support ans action, got {answer!r}")

    letter = await dispatch(ctx, "user-3", "ltr", "")
    if "开字母猜歌" not in letter.value:
        raise SystemExit(f"ltr should start, got {letter!r}")
    opened = await handle_game_reply(ctx, "user-3", "open A")
    if opened is None or ("翻开" not in opened.value and "包含" not in opened.value):
        raise SystemExit(f"listener should support open action, got {opened!r}")
    letter_answer = await handle_game_reply(ctx, "user-3", "ans")
    if letter_answer is None or "公布答案" not in letter_answer.value:
        raise SystemExit(f"listener should reveal ltr answers, got {letter_answer!r}")

    source = (ROOT / "main.py").read_text(encoding="utf-8")
    if "@filter.custom_filter(ActivePhiGameFilter, False)" not in source:
        raise SystemExit("game reply listener should be guarded by ActivePhiGameFilter")
    if "game_reply_listener" not in source:
        raise SystemExit("game reply listener should be configurable")

    print("game reply listener smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
