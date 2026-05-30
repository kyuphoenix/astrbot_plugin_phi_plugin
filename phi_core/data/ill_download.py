from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import PluginConfig
from ..paths import PluginPaths

ILL_REPO_URL = "https://github.com/Catrong/phi-plugin-ill.git"
RESOURCE_REPO_URL = "https://github.com/Catrong/phi-plugin.git"


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
        action = "更新"
    else:
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"曲绘目录已存在但不是 git 仓库：{target}")
        await _run_git(["git", "clone", _repo_url(config), str(target), "--depth=1"])
        action = "下载"
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
    target = paths.cache / "phi-plugin-resource-repo"
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        _run_git_blocking(["git", "-C", str(target), "pull", "--ff-only"])
        action = "更新"
    else:
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"资源缓存目录已存在但不是 git 仓库：{target}")
        _run_git_blocking(["git", "clone", _resource_repo_url(config), str(target), "--depth=1", "--filter=blob:none", "--sparse"])
        _run_git_blocking(["git", "-C", str(target), "sparse-checkout", "set", "resources"])
        action = "下载"
    _copy_resource_tree(target / "resources", paths.downloaded_resources)
    commit = _run_git_blocking(["git", "-C", str(target), "rev-parse", "--short", "HEAD"])
    return ResourceUpdateResult(action=action, target=str(paths.downloaded_resources), commit=commit.strip())


async def update_resources(config: PluginConfig, paths: PluginPaths) -> ResourceUpdateResult:
    target = paths.cache / "phi-plugin-resource-repo"
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        await _run_git(["git", "-C", str(target), "pull", "--ff-only"])
        action = "更新"
    else:
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"资源缓存目录已存在但不是 git 仓库：{target}")
        await _run_git(["git", "clone", _resource_repo_url(config), str(target), "--depth=1", "--filter=blob:none", "--sparse"])
        await _run_git(["git", "-C", str(target), "sparse-checkout", "set", "resources"])
        action = "下载"
    _copy_resource_tree(target / "resources", paths.downloaded_resources)
    commit = await _run_git(["git", "-C", str(target), "rev-parse", "--short", "HEAD"])
    return ResourceUpdateResult(action=action, target=str(paths.downloaded_resources), commit=commit.strip())


def resources_ready(paths: PluginPaths) -> bool:
    required = [
        paths.info / "info.csv",
        paths.info / "difficulty.csv",
        paths.info / "help.json",
        paths.resources / "html" / "b19" / "b19.css",
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


def _copy_resource_tree(source: Path, target: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"原版 resources 目录不存在：{source}")
    for name in ("html", "info", "otherill"):
        _copy_directory(source / name, target / name)


def _copy_directory(source: Path, target: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"资源子目录不存在：{source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.read_bytes())


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
