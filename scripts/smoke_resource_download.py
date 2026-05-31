from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.config import PluginConfig
from phi_core.data import ill_download
from phi_core.paths import PluginPaths


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    tmp = ROOT / "data" / "tmp-smoke-resource-download"
    if tmp.exists():
        shutil.rmtree(tmp)
    paths = PluginPaths.from_root(ROOT, tmp / "data")
    paths.ensure_data_dir()

    resource_repo = paths.cache / "phi-plugin-resource-repo"
    html_repo = paths.cache / "phi-plugin-jinja2-template-repo"
    write(resource_repo / ".git" / "HEAD")
    write(resource_repo / "resources" / "info" / "info.csv", "id,song\n")
    write(resource_repo / "resources" / "info" / "difficulty.csv", "song,rank\n")
    write(resource_repo / "resources" / "info" / "help.json", "[]")
    write(resource_repo / "resources" / "otherill" / "placeholder.txt")
    write(resource_repo / "resources" / "html" / "should-not-copy.txt")
    write(html_repo / ".git" / "HEAD")
    write(html_repo / "common" / "layout" / "default.html", "<html></html>")
    write(html_repo / "b19" / "b19.html", "<div>b19</div>")
    write(html_repo / "b19" / "b19.css", "body{}")
    write(html_repo / "help" / "help.html", "<div>help</div>")
    write(html_repo / "help" / "help.css", "body{}")
    write(html_repo / "otherimg" / "phigros.png", "fake")
    write(paths.downloads / "html" / "stale.txt", "old")

    calls: list[list[str]] = []

    def fake_git(args: list[str]) -> str:
        calls.append(args)
        if args[-3:] == ["rev-parse", "--short", "HEAD"]:
            if str(resource_repo) in args:
                return "res123"
            if str(html_repo) in args:
                return "html456"
        return ""

    original_run_git_blocking = ill_download._run_git_blocking
    try:
        ill_download._run_git_blocking = fake_git
        result = ill_download.update_resources_blocking(PluginConfig(), paths)
    finally:
        ill_download._run_git_blocking = original_run_git_blocking

    if result.commit != "resources:res123 html:html456":
        raise SystemExit(f"unexpected combined commit: {result.commit!r}")
    if not ill_download.resources_ready(paths):
        raise SystemExit("resources_ready should accept copied Jinja2 html plus original info/otherill")
    if not (paths.downloads / "html" / "b19" / "b19.html").exists():
        raise SystemExit("html templates should be copied from the Jinja2 template repository")
    if (paths.downloads / "html" / "should-not-copy.txt").exists():
        raise SystemExit("html should not be copied from the original phi-plugin resources repository")
    if (paths.downloads / "html" / "stale.txt").exists():
        raise SystemExit("html target should be replaced, not merged with stale files")
    if not (paths.downloads / "info" / "info.csv").exists() or not (paths.downloads / "otherill" / "placeholder.txt").exists():
        raise SystemExit("info and otherill should still come from the original resources repository")
    if not any(call[:4] == ["git", "-C", str(resource_repo), "pull"] for call in calls):
        raise SystemExit("existing original resource cache should be pulled")
    if not any(call[:4] == ["git", "-C", str(html_repo), "pull"] for call in calls):
        raise SystemExit("existing Jinja2 template cache should be pulled")

    shutil.rmtree(tmp, ignore_errors=True)
    print("smoke_resource_download passed")


if __name__ == "__main__":
    main()
