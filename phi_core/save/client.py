from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import PluginConfig
from .codec import SaveNotAvailable


@dataclass(slots=True)
class ApiBindResult:
    api_id: str
    have_api_token: bool | None = None
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class PgrTokenResult:
    token: str
    api_id: str | None = None
    raw: dict[str, Any] | None = None


class PhiApiClient:
    def __init__(self, config: PluginConfig):
        self.config = config

    async def bind_user(
        self,
        user_id: str,
        *,
        token: str | None = None,
        api_id: str | None = None,
        is_global: bool | None = None,
    ) -> ApiBindResult:
        payload = self._platform_payload(user_id)
        if token:
            payload["token"] = token
        if api_id:
            payload["api_user_id"] = str(api_id)
        if is_global is not None:
            payload["isGlobal"] = bool(is_global)
        if "token" not in payload and "api_user_id" not in payload:
            raise SaveNotAvailable("请提供 sessionToken 或查询 ID。")

        data = await self._post("/bind", payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("查询 API 没有返回绑定结果。")
        internal_id = self._extract_api_id(data)
        if internal_id is None:
            raise SaveNotAvailable("查询 API 没有返回 internal_id。")
        have_api_token = data.get("have_api_token")
        return ApiBindResult(
            api_id=str(internal_id),
            have_api_token=have_api_token if isinstance(have_api_token, bool) else None,
            raw=data,
        )

    async def fetch_cloud_save(
        self,
        token: str | None = None,
        user_id: str | None = None,
        api_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if token:
            payload["token"] = token
        elif api_id:
            payload["api_user_id"] = str(api_id)
        if user_id:
            payload.update(self._platform_payload(user_id))
        if "token" not in payload and "api_user_id" not in payload:
            raise SaveNotAvailable("请先绑定 sessionToken 或查询 ID。")

        data = await self._post("/get/cloud/saves", payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("查询 API 没有返回标准化存档对象。")
        return data

    async def get_pgr_token(self, user_id: str, api_token: str) -> PgrTokenResult:
        payload = self._platform_payload(user_id)
        payload["api_token"] = api_token
        data = await self._post("/getPgrToken", payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("查询 API 没有返回登录结果。")
        token = data.get("token") or data.get("sessionToken") or data.get("session")
        if not isinstance(token, str) or not token:
            raise SaveNotAvailable("查询 API 没有返回 sessionToken。")
        return PgrTokenResult(
            token=token,
            api_id=self._extract_api_id(data),
            raw=data,
        )

    @staticmethod
    def _platform_payload(user_id: str) -> dict[str, str]:
        return {
            "platform": "AstrBot",
            "platform_id": str(user_id),
        }

    @staticmethod
    def _extract_api_id(data: dict[str, Any]) -> str | None:
        raw = data.get("internal_id") or data.get("apiId") or data.get("api_id") or data.get("user_id")
        return None if raw is None else str(raw)

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
