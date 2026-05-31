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

from phi_core.commands._rendering import render_jinja_template
from phi_core.commands.common import CommandContext
from phi_core.config import PluginConfig
from phi_core.data import SongCatalog, SongSearcher
from phi_core.paths import PluginPaths
from phi_core.save import PhiApiClient, SaveStore


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
    options = render_calls[0][3] or {}
    if '<link rel="stylesheet"' in html or "<script src=" in html or "@import" in html:
        raise SystemExit("external stylesheet/script references should be inlined")
    if "file:///" in html or "D:\\" in html:
        raise SystemExit("remote t2i html must not contain local paths")
    if "data:image/" not in html:
        raise SystemExit("expected images to be converted to data URIs")
    if "width=900" not in html or options.get("viewport_width") != 900:
        raise SystemExit(f"viewport width was not propagated, options={options!r}")
    if "background: #000 !important" not in html or "contain: paint !important" not in html:
        raise SystemExit("reset CSS was not injected")
    if "Smoke" not in html or "phi help" not in html:
        debug = paths.render_cache / "smoke-jinja-debug.html"
        debug.write_text(html, encoding="utf-8")
        raise SystemExit(f"template data was not rendered; wrote {debug}")
    print("smoke_jinja_render_chain passed")


if __name__ == "__main__":
    asyncio.run(main())

