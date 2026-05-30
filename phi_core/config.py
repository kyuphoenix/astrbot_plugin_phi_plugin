from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class PluginConfig:
    default_global: bool = False
    render_mode: str = "image"
    render_backend: str = "html"
    max_b30: int = 33
    api_base_url: str = "https://phib19.top:8080"
    request_timeout: int = 10
    qrcode_timeout: int = 270
    render_max_retries: int = 2
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
            try:
                value = data.get(key, default)
            except TypeError:
                value = data.get(key)  # type: ignore[call-arg]
                if value is None:
                    value = default
            return default if value is None else value

        render_mode = str(get("render_mode", "image") or "image").strip().casefold()
        if render_mode not in {"image", "text"}:
            render_mode = "image"

        return cls(
            default_global=bool(get("default_global", False)),
            render_mode=render_mode,
            render_backend="html",
            max_b30=max(33, min(50, int(get("max_b30", 33)))),
            api_base_url=str(get("api_base_url", "https://phib19.top:8080")).rstrip("/"),
            request_timeout=max(3, int(get("request_timeout", 10))),
            qrcode_timeout=max(30, min(600, int(get("qrcode_timeout", 270)))),
            render_max_retries=max(0, min(5, int(get("render_max_retries", 2)))),
            github_proxy=str(get("github_proxy", "") or ""),
        )
