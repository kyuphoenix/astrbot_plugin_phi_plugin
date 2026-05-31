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

    async def fetch_history(
        self,
        user_id: str,
        *,
        token: str | None = None,
        api_id: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = self._platform_payload(user_id)
        if token:
            payload["token"] = token
        if api_id:
            payload["api_user_id"] = str(api_id)
        if fields:
            payload["request"] = fields
        data = await self._post("/get/history/history", payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("查询 API 没有返回历史记录对象。")
        return data

    async def set_history(
        self,
        user_id: str,
        history: dict[str, Any],
        *,
        token: str | None = None,
        api_id: str | None = None,
    ) -> None:
        payload = self._platform_payload(user_id)
        if token:
            payload["token"] = token
        if api_id:
            payload["api_user_id"] = str(api_id)
        if "token" not in payload and "api_user_id" not in payload:
            raise SaveNotAvailable("上传历史记录需要 sessionToken 或查询 ID。")
        payload["data"] = history
        await self._post("/set/history", payload)

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

    async def live_info(self) -> str:
        data = await self._get("/live", {})
        return str(data or "")

    async def fetch_taptap_notices(self, limit: int = 1) -> list[dict[str, Any]]:
        xua = {
            "V": "1",
            "PN": "TapTap",
            "VN_CODE": "284001001",
            "LANG": "zh_CN",
        }
        data = await self._get_external(
            "https://api.taptapdada.com/feed/v7/by-group",
            {
                "X-UA": self._urlencoded(xua),
                "type": "official",
                "group_id": "197452",
            },
        )
        if not isinstance(data, dict) or not data.get("success"):
            return []
        raw_data = data.get("data")
        raw_list = raw_data.get("list") if isinstance(raw_data, dict) else []
        if not isinstance(raw_list, list):
            return []
        notices: list[dict[str, Any]] = []
        for item in raw_list[:max(1, int(limit))]:
            if not isinstance(item, dict):
                continue
            moment = item.get("moment") if isinstance(item.get("moment"), dict) else {}
            topic = moment.get("topic") if isinstance(moment.get("topic"), dict) else {}
            sharing = moment.get("sharing") if isinstance(moment.get("sharing"), dict) else {}
            images = topic.get("images") if isinstance(topic.get("images"), list) else []
            image = ""
            if images and isinstance(images[0], dict):
                image = str(images[0].get("original_url") or "")
            notices.append({
                "title": str(topic.get("title") or ""),
                "content": str(topic.get("summary") or ""),
                "date": moment.get("publish_time"),
                "url": str(sharing.get("url") or ""),
                "image": image,
            })
        return notices

    async def fetch_taptap_update_logs(self, limit: int = 1) -> list[dict[str, Any]]:
        xua = {
            "V": "1",
            "PN": "TapTap",
            "VN_CODE": "283021001",
            "LANG": "zh_CN",
        }
        data = await self._get_external(
            "https://api.taptapdada.com/apk/v1/list-by-app",
            {
                "limit": str(max(1, int(limit))),
                "X-UA": self._urlencoded(xua),
                "from": "0",
                "app_id": "165287",
            },
        )
        if not isinstance(data, dict) or not data.get("success"):
            return []
        raw_data = data.get("data")
        raw_list = raw_data.get("list") if isinstance(raw_data, dict) else []
        if not isinstance(raw_list, list):
            return []
        logs: list[dict[str, Any]] = []
        for item in raw_list[:max(1, int(limit))]:
            if not isinstance(item, dict):
                continue
            whatsnew = item.get("whatsnew")
            raw_html = ""
            if isinstance(whatsnew, dict):
                raw_html = str(whatsnew.get("text") or "")
            elif whatsnew is not None:
                raw_html = str(whatsnew)
            logs.append({
                "version": str(item.get("version_label") or ""),
                "versionCode": item.get("version_code"),
                "date": item.get("update_date"),
                "rawHtml": raw_html,
            })
        return logs

    async def fetch_comments_by_song(self, song_id: str) -> list[dict[str, Any]]:
        data = await self._post("/comment/get/bySongId", {"song_id": song_id})
        return data if isinstance(data, list) else []

    async def fetch_comments_by_user(
        self,
        user_id: str,
        *,
        token: str | None = None,
        api_id: str | None = None,
    ) -> list[dict[str, Any]]:
        data = await self._post("/comment/get/byUserId", self._auth_payload(user_id, token=token, api_id=api_id))
        return data if isinstance(data, list) else []

    async def add_comment(self, user_id: str, token: str, comment: dict[str, Any]) -> None:
        payload = self._auth_payload(user_id, token=token, api_id=None)
        payload["data"] = {"comment": comment}
        await self._post("/comment/add", payload)

    async def delete_comment(self, user_id: str, token: str, comment_id: str) -> None:
        payload = self._auth_payload(user_id, token=token, api_id=None)
        payload["comment_id"] = str(comment_id)
        await self._post("/comment/del", payload)

    async def fetch_chart_tags(self, song_id: str, rank: str) -> dict[str, Any]:
        data = await self._post("/chartsTag/get/bySongRank", {"song_id": song_id, "rank": rank})
        return data if isinstance(data, dict) else {}

    async def fetch_chart_tag_names(self) -> list[str]:
        data = await self._get("/chartsTag/get/tagNames", {})
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if str(item).strip()]

    async def fetch_chart_user_votes(
        self,
        user_id: str,
        *,
        token: str | None,
        api_id: str | None,
        song_id: str,
        rank: str,
    ) -> list[str]:
        payload = self._auth_payload(user_id, token=token, api_id=api_id)
        payload["data"] = [{"song_id": song_id, "rank": [rank]}]
        data = await self._post("/chartsTag/get/usersVote", payload)
        if not isinstance(data, list) or not data:
            return []
        first = data[0]
        if not isinstance(first, dict):
            return []
        tags = first.get("tags")
        return [str(item) for item in tags] if isinstance(tags, list) else []

    async def fetch_all_song_acc_avg(
        self,
        song_ids: list[str],
        *,
        min_rks: float,
        max_rks: float,
        b30: bool = False,
    ) -> dict[str, Any]:
        endpoint = "/get/scoreList/allAccAvgB30" if b30 else "/get/scoreList/allAccAvg"
        data = await self._post(endpoint, {
            "songIds": song_ids,
            "minRks": min_rks,
            "maxRks": max_rks,
        })
        return data if isinstance(data, dict) else {}

    async def fetch_ranklist_user(self, user_id: str) -> dict[str, Any]:
        data = await self._post("/get/ranklist/user", self._platform_payload(user_id))
        if not isinstance(data, dict):
            raise SaveNotAvailable("API 没有返回排行榜数据。")
        return data

    async def fetch_ranklist_rank(self, rank: int) -> dict[str, Any]:
        data = await self._post("/get/ranklist/rank", {"request_rank": int(rank)})
        if not isinstance(data, dict):
            raise SaveNotAvailable("API 没有返回排行榜数据。")
        return data

    async def fetch_ranklist_rks_rank(self, rks: float) -> dict[str, Any]:
        data = await self._post("/get/ranklist/rksRank", {"request_rks": float(rks)})
        if not isinstance(data, dict):
            raise SaveNotAvailable("API 没有返回 RKS 排名数据。")
        return data

    async def set_chart_tags(
        self,
        user_id: str,
        *,
        token: str | None,
        api_id: str | None,
        song_id: str,
        rank: str,
        tags: list[str],
    ) -> None:
        payload = self._auth_payload(user_id, token=token, api_id=api_id)
        payload["song_id"] = song_id
        payload["rank"] = rank
        payload["content"] = tags
        await self._post("/chartsTag/set/set", payload)

    @staticmethod
    def _platform_payload(user_id: str) -> dict[str, str]:
        return {
            "platform": "AstrBot",
            "platform_id": str(user_id),
        }

    def _auth_payload(self, user_id: str, *, token: str | None, api_id: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = self._platform_payload(user_id)
        if token:
            payload["token"] = token
        if api_id:
            payload["api_user_id"] = str(api_id)
        if "token" not in payload and "api_user_id" not in payload:
            raise SaveNotAvailable("请先绑定 sessionToken 或查询 ID。")
        return payload

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

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.config.api_base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout, verify=False) as client:
                response = await client.get(url, params=params)
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

    async def _get_external(self, url: str, params: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout, verify=False) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise SaveNotAvailable(f"API 请求失败：{exc}") from exc
        except ValueError as exc:
            raise SaveNotAvailable("API 响应不是有效 JSON。") from exc

    @staticmethod
    def _urlencoded(data: dict[str, str]) -> str:
        from urllib.parse import urlencode

        return urlencode(data)
