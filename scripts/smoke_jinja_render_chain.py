from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from PIL import Image
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JINJA2_TEMPLATES = ROOT.parent / "jinja2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands._rendering import render_jinja_template
from phi_core.commands.common import CommandContext
from phi_core.commands.jrrp import _panel_data as jrrp_panel_data
from phi_core.config import PluginConfig
from phi_core.data import SongCatalog, SongSearcher
from phi_core.paths import PluginPaths
from phi_core.save import PhiApiClient, SaveStore
from phi_core.render import jinja_adapter, jinja_renderer
from phi_core.models import Best30Result, SaveSnapshot, ScoreRecord, Song, SongChart, UserSummary


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (12, 12), color).save(path)


async def main() -> None:
    tmp = ROOT / "data" / "tmp-smoke-jinja"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    paths = PluginPaths.from_root(ROOT, tmp)
    paths.ensure_data_dir()

    if JINJA2_TEMPLATES.exists():
        shutil.copytree(JINJA2_TEMPLATES, paths.resources / "html", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    else:
        _write_image(paths.resources / "html" / "otherimg" / "phigros.png", (1, 2, 3))
        _write_image(paths.resources / "html" / "otherimg" / "icon.png", (4, 5, 6))

    render_calls: list[tuple[str, dict, bool, dict | None]] = []

    async def fake_html_render(html: str, data: dict, return_url: bool = True, options: dict | None = None) -> bytes:
        render_calls.append((html, data, return_url, options))
        output = paths.render_cache / "result.png"
        _write_image(output, (20, 21, 22))
        return output.read_bytes()

    catalog = SongCatalog(songs={}, alias_to_id={})
    ctx = CommandContext(
        config=PluginConfig(render_mode="image"),
        paths=paths,
        catalog=catalog,
        searcher=SongSearcher(catalog),
        store=SaveStore(paths.data_dir),
        client=PhiApiClient(PluginConfig()),
        html_render=fake_html_render,
    )
    image_path = await render_jinja_template(
        ctx,
        "help/help",
        {
            "helpGroup": [
                {
                    "group": "Smoke",
                    "list": [
                        {
                            "title": "phi help",
                            "eg": "phi help",
                            "desc": "Jinja render chain smoke",
                            "img": "phigros.png",
                        }
                    ],
                }
            ],
            "cmdHead": "phi",
            "isMaster": True,
            "background": "html/otherimg/phigros.png",
        },
        "smoke-jinja",
        width=900,
    )

    if not image_path.exists():
        raise SystemExit("rendered image path does not exist")
    if len(render_calls) != 1:
        raise SystemExit(f"expected one render call, got {len(render_calls)}")

    html = render_calls[0][0]
    data = render_calls[0][1]
    options = render_calls[0][3] or {}
    if not data or data.get("cmdHead") != "phi":
        raise SystemExit("AstrBot html_render should receive Jinja2 data")
    if "{{" not in html or "{%" not in html:
        raise SystemExit("AstrBot html_render should receive a Jinja2 template, not fully rendered HTML")
    if '<link rel="stylesheet"' in html or "<script src=" in html or "@import" in html:
        raise SystemExit("external stylesheet/script references should be inlined")
    rendered_html = Environment().from_string(html).render(**data)
    if "file:///" in rendered_html or "D:\\" in rendered_html:
        raise SystemExit("remote t2i html must not contain local paths")
    if "data:image/" not in rendered_html:
        raise SystemExit("expected images to be converted to data URIs")
    if "width=900" not in html or options.get("viewport_width") != 900:
        raise SystemExit(f"viewport width was not propagated, options={options!r}")
    if "background: #000" not in html or "--phi-viewport-width: 900px" not in html:
        raise SystemExit("viewport reset CSS was not injected")
    if "body > :not(.background)" in html:
        raise SystemExit("reset CSS must not override original template child positioning")
    if "Smoke" not in rendered_html or "phi help" not in rendered_html:
        debug = paths.render_cache / "smoke-jinja-debug.html"
        debug.write_text(rendered_html, encoding="utf-8")
        raise SystemExit(f"template data was not rendered; wrote {debug}")

    remote_paths = PluginPaths.from_root(ROOT, tmp / "remote")
    remote_paths.ensure_data_dir()
    remote_paths.illustration_source = "remote"
    remote_paths.illustration_url_proxy = "https://proxy.example"
    if JINJA2_TEMPLATES.exists():
        shutil.copytree(JINJA2_TEMPLATES, remote_paths.resources / "html", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    else:
        _write_image(remote_paths.resources / "html" / "otherimg" / "phigros.png", (1, 2, 3))
        _write_image(remote_paths.resources / "html" / "otherimg" / "icon.png", (4, 5, 6))
    (remote_paths.downloaded_original_ill / "illLow").mkdir(parents=True, exist_ok=True)
    _write_image(remote_paths.downloaded_original_ill / "illLow" / "RemoteSong.Smoke.png", (30, 31, 32))
    song = Song(
        id="RemoteSong.Smoke",
        title="Remote Song",
        composer="Codex",
        illustrator="Codex",
        charts={"EZ": SongChart(rank="EZ", difficulty=1.0, combo=1)},
    )
    remote_data = jinja_adapter.atlas_data(remote_paths, song)
    expected_remote_url = "https://proxy.example/https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illLow/RemoteSong.Smoke.png"
    if expected_remote_url not in remote_data["illustration"]:
        raise SystemExit(f"remote atlas illustration should use proxied GitHub raw URL, got {remote_data['illustration']!r}")
    remote_ctx = CommandContext(
        config=PluginConfig(render_mode="image", github_proxy="https://download-proxy.example"),
        paths=remote_paths,
        catalog=SongCatalog(songs={song.id: song}, alias_to_id={}),
        searcher=SongSearcher(SongCatalog(songs={song.id: song}, alias_to_id={})),
        store=SaveStore(remote_paths.data_dir),
        client=PhiApiClient(PluginConfig()),
    )
    guess_source = remote_ctx.illustration_source(song, download_proxy=True)
    expected_guess_url = "https://download-proxy.example/https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illLow/RemoteSong.Smoke.png"
    if guess_source != expected_guess_url:
        raise SystemExit(f"remote guess should use github_proxy, got {guess_source!r}")
    template_source = remote_ctx.illustration_source(song)
    if template_source != expected_remote_url:
        raise SystemExit(f"remote template illustration should use illustration_url_proxy, got {template_source!r}")
    jrrp_data = jinja_adapter.jrrp_data(remote_paths, jrrp_panel_data(remote_ctx, [88, 0]))
    expected_jrrp_url = "https://proxy.example/https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illLow/ShineAfter.ADeanJocularACE.png"
    if jrrp_data.get("bkg") != expected_jrrp_url:
        raise SystemExit(f"remote jrrp background should use proxied GitHub raw URL, got {jrrp_data.get('bkg')!r}")
    info_snapshot = SaveSnapshot(
        user_id="remote-info",
        ranking_score=12.34,
        raw={
            "gameuser": {"background": "Glaciaxion.SunsetRay.0", "name": "Remote Info"},
            "saveInfo": {
                "PlayerId": "REMOTE_INFO",
                "summary": {"rankingScore": 12.34, "challengeModeRank": 512, "avatar": "Introduction"},
            },
            "gameProgress": {"money": [1, 0, 0, 0, 0]},
            "gameRecord": {},
        },
    )
    info_data = jinja_adapter.userinfo_data(
        remote_paths,
        UserSummary("REMOTE_INFO", "Remote Info", 12.34, 512, 123, 0, 0, 0),
        snapshot=info_snapshot,
        history={},
        catalog=catalog,
    )
    expected_info_background = "https://proxy.example/https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illBlur/Glaciaxion.SunsetRay.png"
    if info_data["gameuser"].get("backgroundurl") != expected_info_background:
        raise SystemExit(
            "remote info background should strip the save-id .0 suffix before building the image URL, "
            f"got {info_data['gameuser'].get('backgroundurl')!r}"
        )
    remote_html = jinja_renderer.render_template(remote_paths, "atlas/atlas", remote_data)
    if expected_remote_url not in remote_html:
        raise SystemExit("proxied remote illustration URL should survive Jinja2 self-contained rendering")
    if "data:font/" not in remote_html and "data:application/" not in remote_html:
        raise SystemExit("remote mode should still inline non-illustration font assets")
    if "file:///" in remote_html or "D:\\" in remote_html:
        raise SystemExit("remote mode html must not contain local paths")

    fallback_paths = PluginPaths.from_root(ROOT, tmp / "fallback-ill")
    fallback_paths.ensure_data_dir()
    if JINJA2_TEMPLATES.exists():
        shutil.copytree(JINJA2_TEMPLATES, fallback_paths.resources / "html", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    (fallback_paths.other_ill).mkdir(parents=True, exist_ok=True)
    _write_image(fallback_paths.other_ill / "FallbackA.png", (200, 10, 10))
    _write_image(fallback_paths.other_ill / "FallbackB.png", (10, 200, 10))
    fallback_records = [
        ScoreRecord(
            song_id="MissingA",
            song_title="Missing A",
            rank="IN",
            score=1_000_000,
            acc=100.0,
            fc=True,
            rating="phi",
            difficulty=15.0,
            rks=15.0,
            illustration="FallbackA.png",
        ),
        ScoreRecord(
            song_id="MissingB",
            song_title="Missing B",
            rank="IN",
            score=999_999,
            acc=99.99,
            fc=True,
            rating="FC",
            difficulty=14.0,
            rks=14.0,
            illustration="FallbackB.png",
        ),
    ]
    fallback_snapshot = SaveSnapshot(user_id="fallback", ranking_score=14.5, raw={"gameuser": {}, "saveInfo": {}})
    fallback_result = Best30Result(
        official_rks=14.5,
        computed_rks=14.5,
        records=fallback_records,
        total_records=len(fallback_records),
        phi_records=fallback_records[:1],
    )
    fallback_data = jinja_adapter.adapt_template_data(
        fallback_paths,
        "b19/b19",
        jinja_adapter.b30_data(fallback_paths, fallback_result, fallback_snapshot),
    )
    fallback_images = [
        item["illustration"]
        for item in [*fallback_data["phi"], *fallback_data["b19_list"]]
        if item.get("illustration")
    ]
    if len(set(fallback_images)) < 2:
        raise SystemExit("b30 records should keep per-song fallback illustrations instead of one default image")
    history_lines, history_range, history_dates = jinja_adapter._series_lines(
        {
            "rks": [
                {"date": "2026-01-01 00:00:00", "value": 10},
                {"date": "2026-01-03 00:00:00", "value": 20},
                {"date": "2026-01-04 00:00:00", "value": 20},
                {"date": "2026-01-07 00:00:00", "value": 30},
            ]
        },
        "rks",
    )
    if history_lines != [[0.0, 0.0, 33.33333333333333, 50.0], [33.33333333333333, 50.0, 50.0, 50.0], [50.0, 50.0, 100.0, 100.0]]:
        raise SystemExit(f"history line mapping should match phi-plugin timestamp/range logic, got {history_lines!r}")
    if history_range != [10.0, 30.0] or history_dates != ["2026/01/01 00:00:00", "2026/01/07 00:00:00"]:
        raise SystemExit(f"history range/date mapping mismatch: {history_range!r}, {history_dates!r}")
    acc_records = [
        ScoreRecord("acc-a", "ACC A", "IN", 1_000_000, 100.0, True, "phi", 15.0, 15.0),
        ScoreRecord("acc-b", "ACC B", "IN", 990_000, 99.5, False, "V", 14.8, 14.65),
        ScoreRecord("acc-c", "ACC C", "IN", 970_000, 98.0, False, "V", 14.5, 13.93),
        ScoreRecord("acc-d", "ACC D", "IN", 950_000, 96.2, False, "S", 14.0, 12.97),
        ScoreRecord("acc-e", "ACC E", "IN", 930_000, 94.0, False, "S", 13.5, 11.85),
    ]
    old_iter_score_records = jinja_adapter.iter_score_records
    jinja_adapter.iter_score_records = lambda snapshot, catalog: list(acc_records)
    try:
        acc_lines, acc_range, acc_labels = jinja_adapter._info_acc_rks(fallback_snapshot, catalog)
    finally:
        jinja_adapter.iter_score_records = old_iter_score_records
    if acc_range != [1.0, 2.78] or not acc_lines or round(acc_lines[-1][2], 8) != round(99.83333333338442, 8):
        raise SystemExit(f"Limit-ACC_RKS sampling should stop like phi-plugin before the 100 axis label, got {acc_lines!r}, {acc_range!r}")
    if acc_labels[-1] != [100.0, 100.0]:
        raise SystemExit(f"Limit-ACC_RKS axis labels should still include 100%, got {acc_labels!r}")
    print("smoke_jinja_render_chain passed")


if __name__ == "__main__":
    asyncio.run(main())

