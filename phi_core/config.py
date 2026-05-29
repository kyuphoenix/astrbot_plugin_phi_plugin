from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class PluginConfig:
    default_global: bool = False
    render_mode: str = "image"
    max_b30: int = 30
    api_base_url: str = "https://phib19.top:8080"
    request_timeout: int = 10
    github_proxy: str = ""

    @classmethod
    def from_astrbot(cls, config: Any | None) -> "PluginConfig":
        data: Mapping[str, Any]
        if config is None:
            data = {}
        elif isinstance(config, Mapping):
            data = config
        else:
            try:
                data = dict(config)
            except Exception:
                data = {}

        def get(key: str, default: Any) -> Any:
            value = data.get(key, default)
            return default if value is None else value

        return cls(
            default_global=bool(get("default_global", False)),
            render_mode=str(get("render_mode", "image") or "image"),
            max_b30=max(1, min(50, int(get("max_b30", 30)))),
            api_base_url=str(get("api_base_url", "https://phib19.top:8080")).rstrip("/"),
            request_timeout=max(3, int(get("request_timeout", 10))),
            github_proxy=str(get("github_proxy", "") or ""),
        )
