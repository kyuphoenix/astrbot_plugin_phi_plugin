from __future__ import annotations

from typing import Any

import httpx

from ..config import PluginConfig
from .codec import SaveNotAvailable


class PhiApiClient:
    def __init__(self, config: PluginConfig):
        self.config = config

    async def fetch_cloud_save(self, token: str, user_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"token": token}
        if user_id:
            payload["user_id"] = str(user_id)
            payload["platform"] = "AstrBot"
            payload["platform_id"] = str(user_id)
        data = await self._post("/get/cloud/saves", payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("查询 API 没有返回标准化存档对象。")
        return data

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.config.api_base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout, verify=False) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise SaveNotAvailable(f"API 请求失败：{exc}") from exc
        except ValueError as exc:
            raise SaveNotAvailable("API 响应不是有效 JSON。") from exc

        if isinstance(body, dict) and body.get("error"):
            raise SaveNotAvailable(str(body["error"]))
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body
