from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class PluginConfig:
    default_global: bool = False
    render_mode: str = "image"
    render_backend: str = "html"
    score_image_version: str = "modern"
    ranklist_image_version: str = "modern"
    max_b30: int = 33
    list_score_max_num: int = 80
    history_day_num: int = 10
    history_score_date: int = 10
    history_score_num: int = 50
    api_base_url: str = "https://phib19.top:8080"
    request_timeout: int = 10
    qrcode_timeout: int = 270
    render_max_retries: int = 2
    render_selector_screenshot: bool = True
    render_wait_for_resources: bool = True
    render_resource_timeout: int = 10000
    github_proxy: str = ""
    illustration_source: str = "remote"
    illustration_url_proxy: str = ""
    game_reply_listener: bool = False

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
        score_image_version = str(get("score_image_version", "modern") or "modern").strip().casefold()
        if score_image_version not in {"modern", "old"}:
            score_image_version = "modern"
        ranklist_image_version = str(get("ranklist_image_version", "modern") or "modern").strip().casefold()
        if ranklist_image_version not in {"modern", "old"}:
            ranklist_image_version = "modern"
        illustration_source = str(get("illustration_source", "remote") or "remote").strip().casefold()
        if illustration_source in {"cloud", "online", "github", "url", "urls"}:
            illustration_source = "remote"
        if illustration_source not in {"local", "remote"}:
            illustration_source = "remote"

        return cls(
            default_global=bool(get("default_global", False)),
            render_mode=render_mode,
            render_backend="html",
            score_image_version=score_image_version,
            ranklist_image_version=ranklist_image_version,
            max_b30=max(33, min(50, int(get("max_b30", 33)))),
            list_score_max_num=max(1, min(500, int(get("list_score_max_num", 80)))),
            history_day_num=max(2, min(50, int(get("history_day_num", 10)))),
            history_score_date=max(1, min(60, int(get("history_score_date", 10)))),
            history_score_num=max(1, min(300, int(get("history_score_num", 50)))),
            api_base_url=str(get("api_base_url", "https://phib19.top:8080")).rstrip("/"),
            request_timeout=max(3, int(get("request_timeout", 10))),
            qrcode_timeout=max(30, min(600, int(get("qrcode_timeout", 270)))),
            render_max_retries=max(0, min(5, int(get("render_max_retries", 2)))),
            render_selector_screenshot=bool(get("render_selector_screenshot", True)),
            render_wait_for_resources=bool(get("render_wait_for_resources", True)),
            render_resource_timeout=max(1000, min(60000, int(get("render_resource_timeout", 10000)))),
            github_proxy=str(get("github_proxy", "") or "").strip().rstrip("/"),
            illustration_source=illustration_source,
            illustration_url_proxy=str(get("illustration_url_proxy", "") or "").strip().rstrip("/"),
            game_reply_listener=bool(get("game_reply_listener", False)),
        )
