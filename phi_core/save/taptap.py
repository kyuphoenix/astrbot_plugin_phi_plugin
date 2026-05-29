from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import qrcode

from ..config import PluginConfig
from ..paths import PluginPaths
from .codec import SaveNotAvailable

TAPTAP_CLIENT_ID = "rAK3FfdieFob2Nn8Am"
LC_APP_KEY_CN = "Qr9AEqtuoSVS3zeD6iVbM4ZC0AtkJcQ89tywVyi0"
QrScannedCallback = Callable[[], Awaitable[None] | None]


@dataclass(slots=True)
class TapTapQrRequest:
    device_id: str
    device_code: str
    qrcode_url: str
    expires_in: int
    interval: int
    raw: dict[str, Any]


@dataclass(slots=True)
class TapTapLoginResult:
    session_token: str
    raw: dict[str, Any]


class TapTapQrLogin:
    def __init__(self, config: PluginConfig, paths: PluginPaths):
        self.config = config
        self.paths = paths

    async def request_qrcode(self, *, use_global: bool = False) -> TapTapQrRequest:
        device_id = uuid.uuid4().hex
        payload = {
            "client_id": TAPTAP_CLIENT_ID,
            "response_type": "device_code",
            "scope": "public_profile",
            "version": "2.1",
            "platform": "unity",
            "info": json.dumps({"device_id": device_id}, separators=(",", ":")),
        }
        data = await self._post_form(self._code_url(use_global), payload)
        body = data.get("data") if isinstance(data.get("data"), dict) else data
        if not isinstance(body, dict):
            raise SaveNotAvailable("TapTap 没有返回二维码数据。")
        try:
            return TapTapQrRequest(
                device_id=device_id,
                device_code=str(body["device_code"]),
                qrcode_url=str(body["qrcode_url"]),
                expires_in=int(body.get("expires_in") or 300),
                interval=max(1, int(body.get("interval") or 2)),
                raw=body,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SaveNotAvailable("TapTap 二维码数据不完整。") from exc

    def render_qrcode(self, request: TapTapQrRequest) -> Path:
        self.paths.render_cache.mkdir(parents=True, exist_ok=True)
        path = self.paths.render_cache / f"taptap-qrcode-{uuid.uuid4().hex[:10]}.png"
        image = qrcode.make(request.qrcode_url)
        image.save(path)
        return path

    async def wait_for_session_token(
        self,
        request: TapTapQrRequest,
        *,
        use_global: bool = False,
        on_scanned: QrScannedCallback | None = None,
    ) -> TapTapLoginResult:
        timeout = min(request.expires_in, self.config.qrcode_timeout)
        deadline = time.monotonic() + timeout
        scanned = False
        last_error = ""

        while time.monotonic() < deadline:
            token = await self._check_qrcode(request, use_global=use_global)
            if token.get("success") is True:
                session = await self._get_session_token(token.get("data") or token, use_global=use_global)
                return TapTapLoginResult(session_token=session, raw=token)
            error = str((token.get("data") or {}).get("error") or token.get("error") or "")
            if error == "authorization_waiting":
                if not scanned and on_scanned is not None:
                    maybe_awaitable = on_scanned()
                    if maybe_awaitable is not None:
                        await maybe_awaitable
                scanned = True
            elif error and error != "authorization_pending":
                last_error = error
            await asyncio.sleep(request.interval)

        if scanned:
            raise SaveNotAvailable("二维码已扫描但未确认登录，操作超时。")
        if last_error:
            raise SaveNotAvailable(f"TapTap 登录超时：{last_error}")
        raise SaveNotAvailable("TapTap 二维码登录等待超时。")

    async def _check_qrcode(self, request: TapTapQrRequest, *, use_global: bool) -> dict[str, Any]:
        payload = {
            "grant_type": "device_token",
            "client_id": TAPTAP_CLIENT_ID,
            "secret_type": "hmac-sha-1",
            "code": request.device_code,
            "version": "1.0",
            "platform": "unity",
            "info": json.dumps({"device_id": request.device_id}, separators=(",", ":")),
        }
        data = await self._post_form(self._token_url(use_global), payload)
        if not isinstance(data, dict):
            raise SaveNotAvailable("TapTap 登录轮询没有返回 JSON 对象。")
        return data

    async def _get_session_token(self, token: dict[str, Any], *, use_global: bool) -> str:
        profile = await self._get_profile(token, use_global=use_global)
        profile_data = profile.get("data") if isinstance(profile.get("data"), dict) else profile
        if not isinstance(profile_data, dict):
            raise SaveNotAvailable("TapTap 没有返回账号资料。")
        merged = {**profile_data, **token}
        response = await self._login_leancloud(merged, use_global=use_global)
        session_token = response.get("sessionToken")
        if not isinstance(session_token, str) or not session_token:
            raise SaveNotAvailable("LeanCloud 没有返回 Phigros sessionToken。")
        return session_token

    async def _get_profile(self, token: dict[str, Any], *, use_global: bool) -> dict[str, Any]:
        scope = str(token.get("scope") or "")
        if "public_profile" not in scope:
            raise SaveNotAvailable("TapTap 登录缺少 public_profile 权限。")
        url = self._profile_url(use_global)
        headers = {
            "Authorization": self._authorization_header(
                url,
                "GET",
                str(token.get("kid") or ""),
                str(token.get("mac_key") or ""),
            )
        }
        return await self._request_json("GET", url, headers=headers)

    async def _login_leancloud(self, data: dict[str, Any], *, use_global: bool) -> dict[str, Any]:
        payload = {"authData": {"taptap": data}}
        # The upstream phi-plugin declares global LeanCloud credentials, but
        # still signs requests with the CN client/app pair. Keep that behavior
        # for compatibility while using the matching global endpoint.
        headers = {
            "X-LC-Id": TAPTAP_CLIENT_ID,
            "X-LC-Sign": self._leancloud_sign(LC_APP_KEY_CN),
            "Content-Type": "application/json",
        }
        return await self._request_json("POST", self._leancloud_url(use_global), headers=headers, json_body=payload)

    async def _post_form(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        return await self._request_json("POST", url, data=payload)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout, verify=False) as client:
                response = await client.request(method, url, headers=headers, data=data, json=json_body)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise SaveNotAvailable(f"TapTap 请求失败：{exc}") from exc
        except ValueError as exc:
            raise SaveNotAvailable("TapTap 响应不是有效 JSON。") from exc
        if isinstance(body, dict):
            return body
        raise SaveNotAvailable("TapTap 响应不是 JSON 对象。")

    @staticmethod
    def _authorization_header(request_url: str, method: str, key_id: str, mac_key: str) -> str:
        parsed = httpx.URL(request_url)
        timestamp = str(int(time.time())).rjust(10, "0")
        nonce = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        host = parsed.host or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        # httpx raw_path already includes the query string, matching JS
        # URL.pathname + URL.search used by the original phi-plugin.
        uri = parsed.raw_path.decode("ascii")
        base = f"{timestamp}\n{nonce}\n{method}\n{uri}\n{host}\n{port}\n\n"
        signature = base64.b64encode(hmac.new(mac_key.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")
        return f'MAC id="{key_id}", ts="{timestamp}", nonce="{nonce}", mac="{signature}"'

    @staticmethod
    def _leancloud_sign(app_key: str) -> str:
        timestamp = int(time.time())
        digest = hashlib.md5(f"{timestamp}{app_key}".encode("utf-8")).hexdigest()
        return f"{digest},{timestamp}"

    @staticmethod
    def _code_url(use_global: bool) -> str:
        return f"{'https://accounts.tapapis.com' if use_global else 'https://accounts.tapapis.cn'}/oauth2/v1/device/code"

    @staticmethod
    def _token_url(use_global: bool) -> str:
        return f"{'https://accounts.tapapis.com' if use_global else 'https://accounts.tapapis.cn'}/oauth2/v1/token"

    @staticmethod
    def _profile_url(use_global: bool) -> str:
        host = "https://open.tapapis.com" if use_global else "https://open.tapapis.cn"
        return f"{host}/account/profile/v1?client_id={TAPTAP_CLIENT_ID}"

    @staticmethod
    def _leancloud_url(use_global: bool) -> str:
        base = "https://kviehlel.cloud.ap-sg.tapapis.com/1.1" if use_global else "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1"
        return f"{base}/users"
