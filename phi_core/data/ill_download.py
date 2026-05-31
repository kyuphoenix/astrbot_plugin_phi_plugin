from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import PluginConfig
from ..paths import PluginPaths

ILL_REPO_URL = "https://github.com/Catrong/phi-plugin-ill.git"
RESOURCE_REPO_URL = "https://github.com/Catrong/phi-plugin.git"
HTML_TEMPLATE_REPO_URL = "https://github.com/kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template.git"

ACTION_DOWNLOAD = "download"
ACTION_UPDATE = "update"


@dataclass(slots=True)
class IllustrationUpdateResult:
    action: str
    target: str
    commit: str = ""
    message: str = ""


@dataclass(slots=True)
class ResourceUpdateResult:
    action: str
    target: str
    commit: str = ""


async def update_illustrations(config: PluginConfig, paths: PluginPaths) -> IllustrationUpdateResult:
    target = paths.downloaded_original_ill
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        await _run_git(["git", "-C", str(target), "pull", "--ff-only"])
        action = ACTION_UPDATE
    else:
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"illustration directory exists but is not a git repository: {target}")
        await _run_git(["git", "clone", _repo_url(config), str(target), "--depth=1"])
        action = ACTION_DOWNLOAD
    commit = await _run_git(["git", "-C", str(target), "rev-parse", "--short", "HEAD"])
    return IllustrationUpdateResult(action=action, target=str(target), commit=commit.strip())


async def ensure_resources(config: PluginConfig, paths: PluginPaths) -> ResourceUpdateResult | None:
    if resources_ready(paths):
        return None
    return await update_resources(config, paths)


def ensure_resources_blocking(config: PluginConfig, paths: PluginPaths) -> ResourceUpdateResult | None:
    if resources_ready(paths):
        return None
    return update_resources_blocking(config, paths)


def update_resources_blocking(config: PluginConfig, paths: PluginPaths) -> ResourceUpdateResult:
    resource_repo = paths.cache / "phi-plugin-resource-repo"
    html_repo = paths.cache / "phi-plugin-jinja2-template-repo"
    resource_action = _ensure_resource_repo_blocking(config, resource_repo)
    html_action = _ensure_html_template_repo_blocking(config, html_repo)
    _copy_static_resource_tree(resource_repo / "resources", paths.downloaded_resources)
    _copy_html_template_tree(html_repo, paths.downloaded_resources / "html")
    resource_commit = _run_git_blocking(["git", "-C", str(resource_repo), "rev-parse", "--short", "HEAD"]).strip()
    html_commit = _run_git_blocking(["git", "-C", str(html_repo), "rev-parse", "--short", "HEAD"]).strip()
    return ResourceUpdateResult(
        action=_combined_action(resource_action, html_action),
        target=str(paths.downloaded_resources),
        commit=f"resources:{resource_commit} html:{html_commit}",
    )


async def update_resources(config: PluginConfig, paths: PluginPaths) -> ResourceUpdateResult:
    resource_repo = paths.cache / "phi-plugin-resource-repo"
    html_repo = paths.cache / "phi-plugin-jinja2-template-repo"
    resource_action = await _ensure_resource_repo(config, resource_repo)
    html_action = await _ensure_html_template_repo(config, html_repo)
    _copy_static_resource_tree(resource_repo / "resources", paths.downloaded_resources)
    _copy_html_template_tree(html_repo, paths.downloaded_resources / "html")
    resource_commit = (await _run_git(["git", "-C", str(resource_repo), "rev-parse", "--short", "HEAD"])).strip()
    html_commit = (await _run_git(["git", "-C", str(html_repo), "rev-parse", "--short", "HEAD"])).strip()
    return ResourceUpdateResult(
        action=_combined_action(resource_action, html_action),
        target=str(paths.downloaded_resources),
        commit=f"resources:{resource_commit} html:{html_commit}",
    )


def resources_ready(paths: PluginPaths) -> bool:
    required = [
        paths.info / "info.csv",
        paths.info / "difficulty.csv",
        paths.info / "help.json",
        paths.resources / "html" / "b19" / "b19.html",
        paths.resources / "html" / "b19" / "b19.css",
        paths.resources / "html" / "help" / "help.html",
        paths.resources / "html" / "help" / "help.css",
        paths.resources / "html" / "otherimg" / "phigros.png",
        paths.other_ill,
    ]
    return all(path.exists() for path in required)


def _repo_url(config: PluginConfig) -> str:
    if not config.github_proxy:
        return ILL_REPO_URL
    return f"{config.github_proxy.rstrip('/')}/{ILL_REPO_URL}"


def _resource_repo_url(config: PluginConfig) -> str:
    if not config.github_proxy:
        return RESOURCE_REPO_URL
    return f"{config.github_proxy.rstrip('/')}/{RESOURCE_REPO_URL}"


def _html_template_repo_url(config: PluginConfig) -> str:
    if not config.github_proxy:
        return HTML_TEMPLATE_REPO_URL
    return f"{config.github_proxy.rstrip('/')}/{HTML_TEMPLATE_REPO_URL}"


async def _ensure_resource_repo(config: PluginConfig, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        await _run_git(["git", "-C", str(target), "pull", "--ff-only"])
        return ACTION_UPDATE
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"resource cache directory exists but is not a git repository: {target}")
    await _run_git(["git", "clone", _resource_repo_url(config), str(target), "--depth=1", "--filter=blob:none", "--sparse"])
    await _run_git(["git", "-C", str(target), "sparse-checkout", "set", "resources"])
    return ACTION_DOWNLOAD


def _ensure_resource_repo_blocking(config: PluginConfig, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        _run_git_blocking(["git", "-C", str(target), "pull", "--ff-only"])
        return ACTION_UPDATE
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"resource cache directory exists but is not a git repository: {target}")
    _run_git_blocking(["git", "clone", _resource_repo_url(config), str(target), "--depth=1", "--filter=blob:none", "--sparse"])
    _run_git_blocking(["git", "-C", str(target), "sparse-checkout", "set", "resources"])
    return ACTION_DOWNLOAD


async def _ensure_html_template_repo(config: PluginConfig, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        await _run_git(["git", "-C", str(target), "pull", "--ff-only"])
        return ACTION_UPDATE
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"html template cache directory exists but is not a git repository: {target}")
    await _run_git(["git", "clone", _html_template_repo_url(config), str(target), "--depth=1"])
    return ACTION_DOWNLOAD


def _ensure_html_template_repo_blocking(config: PluginConfig, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        _run_git_blocking(["git", "-C", str(target), "pull", "--ff-only"])
        return ACTION_UPDATE
    if target.exists() and any(target.iterdir()):
        raise RuntimeError(f"html template cache directory exists but is not a git repository: {target}")
    _run_git_blocking(["git", "clone", _html_template_repo_url(config), str(target), "--depth=1"])
    return ACTION_DOWNLOAD


def _copy_static_resource_tree(source: Path, target: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"upstream resources directory does not exist: {source}")
    for name in ("info", "otherill"):
        _copy_directory(source / name, target / name)


def _copy_html_template_tree(source: Path, target: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"html template directory does not exist: {source}")
    _copy_directory(source, target, exclude_names={".git"})


def _copy_directory(source: Path, target: Path, *, exclude_names: set[str] | None = None) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"resource subdirectory does not exist: {source}")
    exclude_names = exclude_names or set()
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if any(part in exclude_names for part in relative.parts):
            continue
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.read_bytes())


def _combined_action(*actions: str) -> str:
    return ACTION_UPDATE if ACTION_UPDATE in actions else ACTION_DOWNLOAD


async def _run_git(args: list[str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        detail = err or out or f"git exited with {process.returncode}"
        raise RuntimeError(detail)
    return out


def _run_git_blocking(args: list[str]) -> str:
    process = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (process.stdout or "").strip()
    err = (process.stderr or "").strip()
    if process.returncode != 0:
        detail = err or out or f"git exited with {process.returncode}"
        raise RuntimeError(detail)
    return out
