from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..config import PluginConfig
from ..paths import PluginPaths

ILL_REPO_URL = "https://github.com/Catrong/phi-plugin-ill.git"


@dataclass(slots=True)
class IllustrationUpdateResult:
    action: str
    target: str
    commit: str = ""
    message: str = ""


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


def _repo_url(config: PluginConfig) -> str:
    if not config.github_proxy:
        return ILL_REPO_URL
    return f"{config.github_proxy.rstrip('/')}/{ILL_REPO_URL}"


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
