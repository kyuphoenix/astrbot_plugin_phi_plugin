from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
JINJA2_TEMPLATES = ROOT.parent / "jinja2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, dispatch
from phi_core.commands.common import CommandResult
from phi_core.config import PluginConfig
from phi_core.data import SongCatalog, SongSearcher
from phi_core.models import Song, SongChart
from phi_core.paths import PluginPaths
from phi_core.save import PhiApiClient, SaveStore


def _write_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


async def main() -> None:
    tmp = ROOT / "data" / "tmp-smoke-guess-answer"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    paths = PluginPaths.from_root(ROOT, tmp)
    paths.ensure_data_dir()

    if JINJA2_TEMPLATES.exists():
        shutil.copytree(JINJA2_TEMPLATES, paths.resources / "html", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    else:
        _write_image(paths.resources / "html" / "otherimg" / "phigros.png", (16, 9), (1, 2, 3))

    song = Song(
        id="Glaciaxion.SunsetRay",
        title="Glaciaxion",
        composer="SunsetRay",
        illustrator="Tetrajectory",
        bpm="128",
        length="02:00",
        chapter="Single",
        charts={"EZ": SongChart(rank="EZ", difficulty=1.0, difficulty_text="1.0", charter="Smoke", combo=100)},
    )
    catalog = SongCatalog(songs={song.id: song}, alias_to_id={"glaciaxion": song.id})
    _write_image(paths.downloaded_original_ill / "ill" / f"{song.id}.png", (2048, 1080), (20, 90, 160))
    _write_image(paths.downloaded_original_ill / "illLow" / f"{song.id}.png", (512, 270), (20, 90, 160))

    render_calls: list[tuple[str, dict, bool, dict | None]] = []
    render_started: list[dict | None] = []
    release_first_answer_render = asyncio.Event()
    answer_render_started = 0
    concurrent_answer_render = False

    async def fake_html_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
        nonlocal answer_render_started, concurrent_answer_render
        render_calls.append((template, data, return_url, options))
        call_index = len(render_calls)
        render_started.append(options)
        if len(render_calls) >= 2:
            answer_render_started += 1
            if answer_render_started == 1:
                await release_first_answer_render.wait()
            else:
                concurrent_answer_render = True
                release_first_answer_render.set()
        output = paths.render_cache / f"guess-render-{call_index}.png"
        _write_image(output, (1200, 800), (8, 24, 50))
        return str(output)

    sent: list[CommandResult] = []

    async def sender(result: CommandResult) -> None:
        sent.append(result)

    ctx = CommandContext(
        config=PluginConfig(render_mode="image", render_backend="html"),
        paths=paths,
        catalog=catalog,
        searcher=SongSearcher(catalog),
        store=SaveStore(paths.data_dir),
        client=PhiApiClient(PluginConfig()),
        html_render=fake_html_render,
        sender=sender,
    )

    started = await dispatch(ctx, "guess-user", "guess", "")
    if started.kind != "image":
        raise SystemExit(f"guess should start with an image, got {started!r}")
    try:
        answered = await asyncio.wait_for(dispatch(ctx, "guess-user", "guess", "Glaciaxion"), timeout=5)
    except TimeoutError as exc:
        raise SystemExit("guess answer render did not run concurrently") from exc
    if answered.kind != "image":
        raise SystemExit(f"guess answer should return atlas image, got {answered!r}")
    if len(render_calls) != 3:
        raise SystemExit(f"expected start/reveal/atlas render calls, got {len(render_calls)}")
    if not concurrent_answer_render:
        raise SystemExit("guess answer should request reveal and atlas renders concurrently")

    reveal_options = render_calls[1][3] or {}
    atlas_options = render_calls[2][3] or {}
    if reveal_options.get("viewport_width") != 2048 or reveal_options.get("viewport_height") != 1080:
        raise SystemExit(f"guess reveal should use 2048x1080 viewport, got {reveal_options!r}")
    if atlas_options.get("viewport_width") != 2048:
        raise SystemExit(f"guess answer atlas should use 2048px viewport, got {atlas_options!r}")
    if len(sent) < 3 or sent[-2].kind != "text" or sent[-1].kind != "image":
        raise SystemExit(f"guess answer should send text and reveal image before atlas, got {sent!r}")

    print("guess answer render viewport smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
