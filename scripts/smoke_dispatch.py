from __future__ import annotations

import asyncio
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_RESOURCES = ROOT.parent / "phi-plugin" / "resources"
JINJA2_TEMPLATES = ROOT.parent / "jinja2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, ROUTE_MODULES, dispatch
from phi_core.config import PluginConfig
from phi_core.data.illustrations import find_background_illustration_file, random_background_source
from phi_core.data import SongSearcher, load_catalog
from phi_core.models import Best30Result, SaveSnapshot, ScoreRecord
from phi_core.paths import PluginPaths
from phi_core.query import random_challenge
from phi_core.render import html_renderer, original, panel
from phi_core.save import ApiBindResult, PgrTokenResult, PhiApiClient, SaveStore, TapTapLoginResult, TapTapQrLogin, TapTapQrRequest
from phi_core.save.taptap import _is_oauth_waiting_response


def _render_call_html(call: tuple[str, dict, bool, dict | None]) -> str:
    template, data, _return_url, _options = call
    cache_key = id(call)
    cached = getattr(_render_call_html, "_cache", None)
    if cached is None:
        cached = {}
        setattr(_render_call_html, "_cache", cached)
    if cache_key not in cached:
        cached[cache_key] = Environment().from_string(template).render(**(data or {}))
    return cached[cache_key]


class FakeLoginClient(PhiApiClient):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.bind_calls: list[dict[str, object | None]] = []
        self.save_counter = 0
        self.history_uploads: list[dict] = []
        self.added_comments: list[dict] = []
        self.deleted_comments: list[str] = []
        self.set_tags: list[dict] = []
        self.history_fetches: list[dict[str, object]] = []
        self.ranklist_rank_requests: list[int] = []
        self.ranklist_rks_requests: list[float] = []
        self.score_ranklist_requests: list[dict[str, object]] = []
        self.song_apfc_requests: list[str] = []
        self.songs_apfc_requests: list[dict[str, object]] = []
        self.set_api_token_calls: list[dict[str, str]] = []
        self.token_list_calls: list[dict[str, str]] = []

    async def bind_user(self, user_id: str, *, token=None, api_id=None, is_global=None):  # type: ignore[override]
        self.bind_calls.append({"user_id": user_id, "token": token, "api_id": api_id, "is_global": is_global})
        return ApiBindResult(api_id=str(api_id or "67890"), have_api_token=False)

    async def get_pgr_token(self, user_id: str, api_token: str):  # type: ignore[override]
        return PgrTokenResult(token="B" * 25, api_id="24680")

    async def set_api_token(self, user_id: str, token: str, api_token: str):  # type: ignore[override]
        self.set_api_token_calls.append({"user_id": user_id, "token": token, "api_token": api_token})
        return {"message": "ok"}

    async def token_list(self, user_id: str, token: str):  # type: ignore[override]
        self.token_list_calls.append({"user_id": user_id, "token": token})
        return {
            "platform_data": [
                {
                    "platform_name": "AstrBot",
                    "platform_id": user_id,
                    "create_at": "2026-05-29",
                    "update_at": "2026-05-30",
                    "authentication": "self",
                },
                {
                    "platform_name": "QQ",
                    "platform_id": "12345",
                    "create_at": "2026-05-01",
                    "update_at": "2026-05-02",
                    "authentication": "normal",
                },
            ]
        }

    async def fetch_cloud_save(self, token=None, user_id=None, api_id=None):  # type: ignore[override]
        self.save_counter += 1
        return sample_save(
            rks=12.3456 + self.save_counter / 10000,
            score=950000 + self.save_counter,
            acc=98.5 + self.save_counter / 100,
            modified=f"2026-05-29T12:00:{self.save_counter:02d}+00:00",
            api_id=str(api_id or "67890"),
            token=str(token or "A" * 25),
        )

    async def fetch_all_song_acc_avg(self, song_ids, *, min_rks, max_rks, b30=False):  # type: ignore[override]
        return {
            str(song_id): {
                "EZ": {"accAvg": 99.4321, "count": 20},
                "HD": {"accAvg": 99.1234, "count": 20},
                "IN": {"accAvg": 98.7654, "count": 20},
                "AT": {"accAvg": 98.4567, "count": 20},
            }
            for song_id in song_ids
        }

    async def fetch_history(self, user_id: str, *, token=None, api_id=None, fields=None):  # type: ignore[override]
        self.history_fetches.append({"user_id": user_id, "token": token, "api_id": api_id, "fields": fields})
        return {
            "rks": [
                {"date": f"2026-04-{index + 1:02d}T00:00:00+00:00", "value": 10 + index / 100}
                for index in range(28)
            ],
            "data": [
                {"date": f"2026-04-{index + 1:02d}T00:00:00+00:00", "value": [index, 2, 0, 0, 0]}
                for index in range(28)
            ],
            "challengeModeRank": [],
            "scoreHistory": {},
        }

    async def set_history(self, user_id: str, history: dict, *, token=None, api_id=None):  # type: ignore[override]
        self.history_uploads.append(history)

    async def live_info(self):  # type: ignore[override]
        return "Smoke Live"

    async def fetch_taptap_notices(self, limit: int = 1):  # type: ignore[override]
        return [{
            "title": "Smoke TapTap Notice",
            "content": "online notice body",
            "date": 1779468654,
            "url": "https://www.taptap.cn/app/165287/topic",
            "image": "",
        }]

    async def fetch_taptap_update_logs(self, limit: int = 1):  # type: ignore[override]
        return [{
            "version": "Smoke 9.9.9",
            "versionCode": 999,
            "date": 1779468654,
            "rawHtml": "<div>Smoke TapTap Update<br/>鏂板涓ら鍗曟洸锛?br/>鈥€孲now Dance銆?by 鎮犲彾銇勩伄銈?br/>鈥€屼簜鈽呰垶銆?by Nekock路LK</div>",
        }]

    async def fetch_comments_by_song(self, song_id: str):  # type: ignore[override]
        return [{"id": "7", "songId": song_id, "rank": "EZ", "PlayerId": "SMOKE", "comment": "hello", "time": "2026-05-29"}]

    async def fetch_comments_by_user(self, user_id: str, *, token=None, api_id=None):  # type: ignore[override]
        return [{"id": "7", "songId": "Glaciaxion.SunsetRay", "rank": "EZ", "comment": "hello", "time": "2026-05-29"}]

    async def add_comment(self, user_id: str, token: str, comment: dict):  # type: ignore[override]
        self.added_comments.append(comment)

    async def delete_comment(self, user_id: str, token: str, comment_id: str):  # type: ignore[override]
        self.deleted_comments.append(comment_id)

    async def fetch_chart_tags(self, song_id: str, rank: str):  # type: ignore[override]
        return {"节奏": 3, "配置": 2}

    async def fetch_chart_tag_names(self):  # type: ignore[override]
        return ["节奏", "配置", "读谱"]

    async def fetch_chart_user_votes(self, user_id: str, *, token=None, api_id=None, song_id: str, rank: str):  # type: ignore[override]
        return ["节奏"]

    async def set_chart_tags(self, user_id: str, *, token=None, api_id=None, song_id: str, rank: str, tags: list[str]):  # type: ignore[override]
        self.set_tags.append({"song_id": song_id, "rank": rank, "tags": tags})

    async def fetch_ranklist_user(self, user_id: str):  # type: ignore[override]
        return self._ranklist_payload(me_index=3)

    async def fetch_ranklist_rank(self, rank: int):  # type: ignore[override]
        self.ranklist_rank_requests.append(rank)
        return self._ranklist_payload(me_index=max(1, rank))

    async def fetch_ranklist_rks_rank(self, rks: float):  # type: ignore[override]
        self.ranklist_rks_requests.append(rks)
        return {"rksRank": 12, "totNum": 345}

    async def fetch_score_ranklist_user(self, user_id: str, *, token=None, api_id=None, song_id: str, rank: str, order_by: str = "acc"):  # type: ignore[override]
        self.score_ranklist_requests.append({"user_id": user_id, "song_id": song_id, "rank": rank, "order_by": order_by})
        users = []
        for index in range(1, 5):
            users.append({
                "index": index,
                "gameuser": {
                    "PlayerId": f"SCORE_USER_{index}",
                    "rankingScore": 12.5 - index / 100,
                    "challengeModeRank": 500 + index,
                    "avatar": "Introduction",
                },
                "record": {
                    "score": 990000 - index,
                    "acc": 99.5 - index / 100,
                    "fc": index % 2 == 0,
                    "updated_at": 1779468654 + index,
                },
            })
        return {"totDataNum": 456, "userRank": 2, "users": users}

    async def fetch_song_ap_fc_count(self, song_id: str):  # type: ignore[override]
        self.song_apfc_requests.append(song_id)
        return {
            "EZ": {"apCount": 1, "fcCount": 2, "total": 4},
            "HD": {"apCount": 2, "fcCount": 3, "total": 5},
            "IN": {"apCount": 3, "fcCount": 4, "total": 6},
        }

    async def fetch_songs_ap_fc_count(self, song_ids, *, ranks, min_rks, max_rks):  # type: ignore[override]
        self.songs_apfc_requests.append({
            "song_ids": list(song_ids),
            "ranks": list(ranks),
            "min_rks": min_rks,
            "max_rks": max_rks,
        })
        return {
            str(song_id): {
                "EZ": {"apCount": 1, "fcCount": 2, "total": 4},
                "HD": {"apCount": 2, "fcCount": 3, "total": 5},
                "IN": {"apCount": 3, "fcCount": 4, "total": 6},
                "AT": {"apCount": 4, "fcCount": 5, "total": 7},
            }
            for song_id in song_ids
        }

    def _ranklist_payload(self, *, me_index: int) -> dict:
        users = []
        for offset in range(5):
            index = max(1, me_index - 2 + offset)
            users.append({
                "index": index,
                "me": index == me_index,
                **sample_save(
                    rks=12.6 - index / 100,
                    score=960000 + index,
                    acc=98.6 + index / 100,
                    modified=f"2026-05-{20 + offset:02d}T12:00:00+00:00",
                    api_id=str(70000 + index),
                    token="R" * 25,
                ),
            })
        return {
            "totDataNum": 345,
            "users": users,
            "me": {
                "save": sample_save(
                    rks=12.5432,
                    score=980000,
                    acc=99.2,
                    modified="2026-05-29T12:00:00+00:00",
                    api_id="76543",
                    token="R" * 25,
                ),
                "history": {
                    "rks": [
                        {"date": f"2026-05-{index + 1:02d}T00:00:00+00:00", "value": 12 + index / 100}
                        for index in range(18)
                    ],
                    "challengeModeRank": [
                        {"date": f"2026-05-{index + 1:02d}T00:00:00+00:00", "value": 500 + index}
                        for index in range(8)
                    ],
                },
            },
        }


class FakeTapTapLogin(TapTapQrLogin):
    def __init__(self, config: PluginConfig, paths: PluginPaths):
        super().__init__(config, paths)
        self.request_use_global: bool | None = None
        self.wait_use_global: bool | None = None

    async def request_qrcode(self, *, use_global: bool = False):  # type: ignore[override]
        self.request_use_global = use_global
        return TapTapQrRequest(
            device_id="device",
            device_code="code",
            qrcode_url="https://example.com/qrcode",
            expires_in=120,
            interval=1,
            raw={},
        )

    async def wait_for_session_token(self, request: TapTapQrRequest, *, use_global: bool = False, on_scanned=None):  # type: ignore[override]
        self.wait_use_global = use_global
        if on_scanned is not None:
            maybe_awaitable = on_scanned()
            if maybe_awaitable is not None:
                await maybe_awaitable
        return TapTapLoginResult(session_token="D" * 25, raw={})


class FakeProgressClient(PhiApiClient):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.history_fetches: list[dict[str, object]] = []
        self.saves = [
            sample_save(rks=11.1111, score=930000, acc=96.5, modified="2026-05-29T13:00:00+00:00"),
            sample_save(rks=11.2222, score=970000, acc=99.1, modified="2026-05-29T14:00:00+00:00"),
        ]

    async def fetch_cloud_save(self, token=None, user_id=None, api_id=None):  # type: ignore[override]
        if len(self.saves) > 1:
            return self.saves.pop(0)
        return self.saves[0]

    async def fetch_history(self, user_id: str, *, token=None, api_id=None, fields=None):  # type: ignore[override]
        self.history_fetches.append({"user_id": user_id, "token": token, "api_id": api_id, "fields": fields})
        return {}

    async def set_history(self, user_id: str, history: dict, *, token=None, api_id=None):  # type: ignore[override]
        return None


class TokenOnlyProgressClient(FakeProgressClient):
    async def fetch_cloud_save(self, token=None, user_id=None, api_id=None):  # type: ignore[override]
        return sample_save(rks=11.1111, score=930000, acc=96.5, modified="2026-05-29T13:00:00+00:00", api_id="")


class EmptyLiveClient(PhiApiClient):
    async def live_info(self):  # type: ignore[override]
        return ""


def sample_save(
    *,
    rks: float,
    score: int,
    acc: float,
    modified: str,
    api_id: str = "67890",
    token: str = "A" * 25,
) -> dict:
    return {
        "session": token,
        "internal_id": api_id,
        "saveInfo": {
            "PlayerId": "SMOKE_PLAYER",
            "modifiedAt": {"iso": modified},
            "summary": {
                "rankingScore": rks,
                "challengeModeRank": 512,
                "gameVersion": 123,
                "updatedAt": modified,
            },
        },
        "gameuser": {"name": "Smoke Tester"},
        "gameProgress": {"money": [1, 2, 0, 0, 0]},
        "gameRecord": {
            "Glaciaxion.SunsetRay": [
                {"score": score, "acc": acc, "fc": False},
                {"score": 990000, "acc": 99.8, "fc": True},
                {"score": 0, "acc": 0, "fc": False},
            ]
        },
    }


def install_resource_fixture(paths: PluginPaths) -> None:
    if not UPSTREAM_RESOURCES.exists():
        raise SystemExit(f"missing upstream resource fixture: {UPSTREAM_RESOURCES}")
    for name in ("info", "otherill"):
        shutil.copytree(UPSTREAM_RESOURCES / name, paths.downloads / name, dirs_exist_ok=True)
    if not JINJA2_TEMPLATES.exists():
        raise SystemExit(f"missing Jinja2 template fixture: {JINJA2_TEMPLATES}")
    shutil.copytree(JINJA2_TEMPLATES, paths.downloads / "html", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))


async def main() -> None:
    data_dir = ROOT / ".tmp_smoke_data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

    try:
        paths = PluginPaths.from_root(ROOT, data_dir=data_dir)
        paths.ensure_data_dir()
        install_resource_fixture(paths)
        downloaded_ill = paths.downloaded_original_ill / "illLow"
        downloaded_ill.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 24), (120, 40, 90)).save(downloaded_ill / "Glaciaxion.SunsetRay.png")
        Image.new("RGB", (32, 24), (80, 120, 40)).save(paths.downloaded_original_ill / "RootOnly.Smoke.png")
        if find_background_illustration_file(paths, "RootOnly.Smoke") is None:
            raise SystemExit("background lookup should also find illustrations saved in original_ill root")
        sample_records = [
            ScoreRecord(
                song_id="Glaciaxion.SunsetRay",
                song_title=f"Smoke Song {index:02d}",
                rank="EZ",
                score=950000 + index,
                acc=98.0 + index / 100,
                fc=False,
                rating="S",
                difficulty=12.0 + index / 100,
                rks=12.0 - index / 100,
            )
            for index in range(45)
        ]
        b30_html = original.b30_html(
            paths,
            Best30Result(
                official_rks=12.3456,
                computed_rks=12.1234,
                records=sample_records,
                total_records=len(sample_records),
                phi_records=[],
            ),
            SaveSnapshot(user_id="smoke", ranking_score=12.3456, raw={"saveInfo": {"modifiedAt": {"iso": "2026-05-29T12:00:00+00:00"}}}),
        )
        if "OVER FLOW" not in b30_html or "#28" not in b30_html:
            raise SystemExit("b30 html should render overflow records after B27")
        if "RKS 12." in b30_html:
            raise SystemExit("b30 html acc-side pill should show push suggestion, not duplicated RKS text")
        if "Real RKS:" not in b30_html:
            raise SystemExit("b30 html should render original Real RKS info chip when computed rks differs")
        if "suggest-tip" not in b30_html or "width: 1200px" not in b30_html:
            raise SystemExit("b30 html should keep original suggestion pill and page-width reset")
        online_paths = PluginPaths.from_root(ROOT, data_dir=data_dir / "no-local-ill")
        online_paths.ensure_data_dir()
        install_resource_fixture(online_paths)
        if online_paths.other_ill.exists():
            shutil.rmtree(online_paths.other_ill)
        online_background = random_background_source(online_paths)
        if not isinstance(online_background, str) or "raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illBlur/" not in online_background:
            raise SystemExit("background picker should fall back to online random blurred illustrations before phigros.png")
        original_remote_loader = original._remote_image_data_uri
        try:
            original._remote_image_data_uri = lambda _paths, _url: "data:image/png;base64,cmVtb3Rl"
            online_help_html = original.help_html(online_paths)
        finally:
            original._remote_image_data_uri = original_remote_loader
        if "data:image/png;base64,cmVtb3Rl" not in online_help_html:
            raise SystemExit("html background should inline online illustration bytes before rendering")
        if "raw.githubusercontent.com" in online_help_html or "file:///" in online_help_html:
            raise SystemExit("html background should not pass remote or local file URLs to t2i")
        online_paths.illustration_source = "remote"
        online_paths.illustration_url_proxy = "https://proxy.example"
        remote_help_html = original.help_html(online_paths)
        if "https://proxy.example/https://raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illBlur/" not in remote_help_html:
            raise SystemExit("remote illustration mode should pass proxied GitHub raw blurred background URLs to templates")
        if "data:image/png;base64,cmVtb3Rl" in remote_help_html:
            raise SystemExit("remote illustration mode should not fetch and base64-encode phi-plugin-ill URLs")
        trim_source = paths.render_cache / "trim-source.png"
        Image.new("RGB", (1280, 32), (0, 0, 0)).save(trim_source)
        with Image.open(trim_source) as image:
            image.paste((20, 80, 120), (0, 0, 1200, 32))
            image.save(trim_source)
        trimmed = panel._render_result_path(paths, str(trim_source), "trim-smoke")
        if trimmed is None:
            raise SystemExit("right-border trim should return an image path")
        with Image.open(trimmed) as image:
            if image.width != 1200:
                raise SystemExit(f"right-border trim should crop blank edge to 1200px, got {image.size}")
        catalog = load_catalog(paths.info)
        old_notes_path = paths.info / "oldNotesInfo.json"
        old_notes = json.loads(old_notes_path.read_text(encoding="utf-8-sig"))
        old_notes["Glaciaxion.SunsetRay"]["EZ"]["t"][0] -= 1
        old_notes_path.write_text(json.dumps(old_notes, ensure_ascii=False), encoding="utf-8")
        newlog_diff_rows = original._newlog_changed_rows(paths, catalog)
        if not any(len(row) == 4 and row[2].get("cnt") == "tap" for row in newlog_diff_rows):
            raise SystemExit("newlog should include tap/drag/hold/flick note-count diffs from oldNotesInfo")
        filtered_challenge = random_challenge(catalog, "30-45 IN (12-15)", rng=random.Random(0))
        if filtered_challenge is None:
            raise SystemExit("randclg should find charts with outer rank and inner chart filters")
        _, challenge_charts = filtered_challenge
        if any(chart.rank != "IN" or chart.difficulty < 12 or chart.difficulty > 15.9 for chart in challenge_charts):
            raise SystemExit(f"randclg did not honor outer/inner filters: {challenge_charts!r}")
        config = PluginConfig(render_mode="text")
        ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )
        ctx.store.bind("smoke-user", "A" * 25, api_id="12345")

        cases = [
            ("help", "", "Phi Plugin Query Core"),
            ("song", "Glaciaxion", "Glaciaxion"),
            ("search", "dif 12 combo 300-600", "当前筛选："),
            ("pgr", "", "还没有可用"),
            ("data", "", "还没有可用"),
            ("id", "", "查询 ID: 12345"),
            ("sessiontoken", "", "AAAA"),
            ("auth", "", "请提供查询平台 API Token"),
            ("sessiontoken", "help", "sessionToken 有关帮助"),
            ("api", "help", "Phi API 帮助"),
            ("best", "", "还没有可用"),
            ("tips", "", ""),
            ("alias", "Glaciaxion", "name: Glaciaxion"),
            ("com", "15.0 99.5", "等效 RKS"),
            ("table", "15", "定数表 15"),
            ("newlog", "", "最新版本"),
            ("rand", "12 IN", "随机谱面："),
            ("randclg", "30-45", "随机课题"),
            ("down", "bad", "格式：phi down resources"),
            ("jrrp", "", "今日人品"),
            ("myset", "", "Phi-Plugin 用户设置"),
            ("theme", "2", "设置成功"),
        ]
        old_table = await dispatch(ctx, "smoke-user", "table", "1 -v 100")
        if "3.5.2" not in old_table.value or "共 5 个谱面" not in old_table.value or "dB doll" not in old_table.value:
            raise SystemExit(f"table -v should render charts from oldInfo/change.csv, got {old_table.value!r}")

        for command, args, expected in cases:
            result = await dispatch(ctx, "smoke-user", command, args)
            if expected and expected not in result.value:
                raise SystemExit(f"{command} expected {expected!r}, got {result.value!r}")
            first_line = result.value.splitlines()[0]
            safe_line = first_line.encode("utf-8", errors="backslashreplace").decode("utf-8")
            print(f"{command}: {safe_line}")

        jrrp_first = await dispatch(ctx, "jrrp-cache-user", "jrrp", "")
        jrrp_second = await dispatch(ctx, "jrrp-cache-user", "jrrp", "")
        if jrrp_first.value != jrrp_second.value:
            raise SystemExit("jrrp should reuse the same cached fortune within one UTC+8 day")

        online_notice_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeLoginClient(config),
        )
        online_notice = await dispatch(online_notice_ctx, "notice-user", "newnotice", "")
        if "Smoke TapTap Notice" not in online_notice.value or "online notice body" not in online_notice.value:
            raise SystemExit(f"newnotice should prefer online TapTap notice data, got {online_notice.value!r}")
        online_newlog = await dispatch(online_notice_ctx, "notice-user", "newlog", "")
        if "Smoke TapTap Update" not in online_newlog.value or "信息文件版本" not in online_newlog.value:
            raise SystemExit(f"newlog should include online TapTap update text, got {online_newlog.value!r}")

        guess_start = await dispatch(ctx, "game-guess-user", "guess", "")
        if "猜曲绘" not in guess_start.value:
            raise SystemExit(f"guess should start illustration game, got {guess_start.value!r}")
        guess_wrong = await dispatch(ctx, "game-guess-user", "guess", "not glaciaxion")
        if "不是" not in guess_wrong.value:
            raise SystemExit(f"guess should reject wrong answer, got {guess_wrong.value!r}")
        guess_right = await dispatch(ctx, "game-guess-user", "guess", "Glaciaxion")
        if "答对" not in guess_right.value or "Glaciaxion" not in guess_right.value:
            raise SystemExit(f"guess should accept correct answer and reveal song, got {guess_right.value!r}")

        tipgame_start = await dispatch(ctx, "game-tip-user", "tipgame", "")
        if "提示猜歌" not in tipgame_start.value or "1." not in tipgame_start.value:
            raise SystemExit(f"tipgame should start with first hint, got {tipgame_start.value!r}")
        tipgame_tip = await dispatch(ctx, "game-tip-user", "tip", "")
        if "2." not in tipgame_tip.value:
            raise SystemExit(f"tip should reveal another tip, got {tipgame_tip.value!r}")
        tipgame_ans = await dispatch(ctx, "game-tip-user", "ans", "")
        if "正确答案" not in tipgame_ans.value or "Glaciaxion" not in tipgame_ans.value:
            raise SystemExit(f"ans should reveal tipgame answer, got {tipgame_ans.value!r}")

        for index, song in enumerate(catalog.all_songs()[:12]):
            path = downloaded_ill / f"{song.id}.png"
            if not path.exists():
                Image.new("RGB", (32, 24), ((index * 37) % 255, (index * 73) % 255, (index * 109) % 255)).save(path)
        letter_start = await dispatch(ctx, "game-letter-user", "ltr", "")
        if "开字母猜歌开启成功" not in letter_start.value or "1." not in letter_start.value:
            raise SystemExit(f"ltr should start letter game, got {letter_start.value!r}")
        letter_open = await dispatch(ctx, "game-letter-user", "open", "A")
        if "字符" not in letter_open.value:
            raise SystemExit(f"open should reveal or report a letter, got {letter_open.value!r}")
        letter_tip = await dispatch(ctx, "game-letter-user", "tip", "")
        if "曲库范围" not in letter_tip.value and "答案如下" not in letter_tip.value:
            raise SystemExit(f"letter tip should update puzzle or finish, got {letter_tip.value!r}")
        letter_ans = await dispatch(ctx, "game-letter-user", "ans", "")
        if "公布答案" not in letter_ans.value or "1." not in letter_ans.value:
            raise SystemExit(f"ans should reveal letter game answers, got {letter_ans.value!r}")

        notes_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeLoginClient(config),
        )
        notes_ctx.store.save_snapshot(
            "notes-user",
            sample_save(
                rks=12.3456,
                score=950000,
                acc=98.5,
                modified="2026-05-29T12:00:00+00:00",
            ),
        )
        sign_result = await dispatch(notes_ctx, "notes-user", "sign", "")
        if "签到成功" not in sign_result.value:
            raise SystemExit(f"sign should grant daily notes, got {sign_result.value!r}")
        notes_data = notes_ctx.store.load_notes("notes-user")
        if notes_data["money"] <= 0 or not notes_data.get("sign_history"):
            raise SystemExit(f"sign should persist money and sign history, got {notes_data!r}")
        task_result = await dispatch(notes_ctx, "notes-user", "task", "")
        if "Phi-Plugin 任务列表" not in task_result.value:
            raise SystemExit(f"task should render task list in text mode, got {task_result.value!r}")
        notes_data["money"] = 50
        notes_ctx.store.save_notes("notes-user", notes_data)
        retask_result = await dispatch(notes_ctx, "notes-user", "retask", "")
        if "任务已刷新" not in retask_result.value:
            raise SystemExit(f"retask should refresh tasks, got {retask_result.value!r}")
        send_result = await dispatch(notes_ctx, "notes-user", "send", "98765 5")
        if "转账成功" not in send_result.value or notes_ctx.store.load_notes("98765")["money"] != 4:
            raise SystemExit(f"send should transfer notes with upstream 80% fee, got {send_result.value!r}")

        if ROUTE_MODULES.get("pgr") != "pgr":
            raise SystemExit(f"pgr route mismatch: {ROUTE_MODULES.get('pgr')}")
        if ctx.store.load_user_settings("smoke-user").get("theme") != "star":
            raise SystemExit("theme command should persist the selected user theme")

        missing_html_ctx = CommandContext(
            config=PluginConfig(render_mode="image", render_backend="html"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )
        try:
            await dispatch(missing_html_ctx, "smoke-user", "help", "")
            raise SystemExit("help image render should fail when AstrBot html_render is missing")
        except RuntimeError as exc:
            if "html_render is not available" not in str(exc):
                raise

        html_diag = html_renderer.backend_diagnostics(paths)
        if not Path(html_diag["template_dir"]).exists():
            raise SystemExit(f"html template dir missing: {html_diag}")
        if not Path(html_diag["font"]).exists():
            raise SystemExit(f"html font missing: {html_diag}")

        html_render_calls: list[tuple[str, dict, bool, dict | None]] = []

        async def fake_html_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
            html_render_calls.append((template, data, return_url, options))
            path = paths.render_cache / "fake-html-render.png"
            Image.new("RGB", (1200, 800), (7, 23, 45)).save(path)
            return str(path)

        retry_calls = 0

        async def flaky_html_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
            nonlocal retry_calls
            retry_calls += 1
            if retry_calls == 1:
                raise RuntimeError("transient t2i disconnect")
            path = paths.render_cache / "fake-retry-render.png"
            Image.new("RGB", (1200, 800), (9, 24, 60)).save(path)
            return str(path)

        retry_path = await panel.render_html(
            PluginConfig(render_mode="image", render_backend="html", render_max_retries=1),
            paths,
            "<html><body>retry</body></html>",
            "retry",
            html_render=flaky_html_render,
        )
        if retry_calls != 2 or not retry_path.exists():
            raise SystemExit("html renderer should retry once after a transient failure")

        html_ctx = CommandContext(
            config=PluginConfig(render_mode="image", render_backend="html"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
            html_render=fake_html_render,
        )
        html_result = await dispatch(html_ctx, "smoke-user", "help", "")
        if html_result.kind != "image" or not Path(html_result.value).exists():
            raise SystemExit(f"official html render path failed: {html_result!r}")
        with Image.open(html_result.value) as rendered:
            if rendered.width < 1000 or rendered.height < 500:
                raise SystemExit(f"help image has unexpected size: {rendered.size}")
        help_template = html_render_calls[0][0]
        help_html = _render_call_html(html_render_calls[0])
        if not html_render_calls or 'class="help_box"' not in help_html or ".help_box" not in help_template:
            raise SystemExit("official html renderer was not called with the original help resources")
        if "{{" not in help_template or not html_render_calls[0][1]:
            raise SystemExit("official html renderer should receive a Jinja2 template and data dict")
        if "file:///" in help_html:
            raise SystemExit("official html renderer should receive self-contained help HTML without local file URLs")
        if "data:image/" not in help_html:
            raise SystemExit("official html renderer should inline local help images as data URIs")
        if "themeStar()" in help_html or "Star1" in help_html:
            raise SystemExit("help html should use random blurred illustration background, not the fixed star theme")
        if "background: #000" not in help_template or "body > :not(.background)" in help_template:
            raise SystemExit("help html should set viewport reset without overriding original template positioning")
        if "position: fixed !important" in help_template or "height: 100vh !important" in help_template:
            raise SystemExit("help html background should be page-height aware, not fixed to the viewport")
        if 'background: url("") center no-repeat' not in help_template:
            raise SystemExit("help html should remove original common.css phigros body fallback before t2i")
        if '<img src="data:image/' not in help_html:
            raise SystemExit("help html should inline the selected illustration into the contained background layer")
        if "background: transparent !important" not in help_template:
            raise SystemExit("help html should not paint the selected illustration as an unblurred body background")
        if "phiAdjustFontSize" not in help_template:
            raise SystemExit("official html renderer should include original auto font sizing script")
        if html_render_calls[0][2] is not False:
            raise SystemExit("official html renderer should return a local file path")
        if "@font-face" not in help_template:
            raise SystemExit("official html renderer should receive inlined original common css resources")
        if html_render_calls[0][3] is None or html_render_calls[0][3].get("type") != "png":
            raise SystemExit("official html renderer should be asked for png output")
        if html_render_calls[0][3].get("viewport_width") != 1200 or html_render_calls[0][3].get("viewport_height") is None:
            raise SystemExit("official html renderer should receive an explicit viewport to avoid reused-context width drift")
        if html_render_calls[0][3].get("scale") != "css":
            raise SystemExit("official html renderer should use css screenshot scale so 1200 CSS pixels are not emitted as high-DPR half-cropped images")
        ill_result = await dispatch(html_ctx, "smoke-user", "ill", "Glaciaxion")
        if ill_result.kind != "image" or not Path(ill_result.value).exists():
            raise SystemExit(f"official ill render path failed: {ill_result!r}")
        if len(html_render_calls) < 2:
            raise SystemExit("phi ill should call official html renderer in image mode")
        ill_html = _render_call_html(html_render_calls[-1])
        if "file:///" in ill_html or "http://raw.githubusercontent" in ill_html or "https://raw.githubusercontent" in ill_html:
            raise SystemExit("phi ill should pass base64 data URIs to t2i, not local or remote URLs")
        if "data:image/" not in ill_html:
            raise SystemExit("phi ill should inline illustration images as data URIs")

        byte_render_calls: list[tuple[str, dict, bool, dict | None]] = []

        async def fake_html_render_bytes(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> bytes:
            byte_render_calls.append((template, data, return_url, options))
            image_path = paths.render_cache / "fake-byte-render-source.png"
            Image.new("RGB", (320, 180), (9, 42, 77)).save(image_path)
            return image_path.read_bytes()

        byte_ctx = CommandContext(
            config=PluginConfig(render_mode="image", render_backend="html"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
            html_render=fake_html_render_bytes,
        )
        byte_result = await dispatch(byte_ctx, "smoke-user", "help", "")
        if byte_result.kind != "image" or not Path(byte_result.value).exists():
            raise SystemExit(f"official html render bytes path failed: {byte_result!r}")
        if not Path(byte_result.value).name.startswith("html-help-"):
            raise SystemExit(f"official html render bytes should be saved into render cache: {byte_result.value}")

        diag_result = await dispatch(html_ctx, "smoke-user", "renderdiag", "")
        if diag_result.kind != "image" or not Path(diag_result.value).exists():
            raise SystemExit(f"renderdiag image render failed: {diag_result!r}")

        pending_body = {"success": False, "data": {"error": "authorization_pending"}}
        if not _is_oauth_waiting_response(pending_body):
            raise SystemExit("TapTap authorization_pending should be treated as a waiting response")

        login_client = FakeLoginClient(config)
        login_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=login_client,
        )

        result = await dispatch(login_ctx, "login-user", "auth", "api-token-123")
        if "登录成功" not in result.value:
            raise SystemExit(f"auth expected success, got {result.value!r}")
        if login_ctx.store.get_token("login-user") != "B" * 25:
            raise SystemExit("auth did not persist returned sessionToken")
        if login_ctx.store.get_api_id("login-user") != "24680":
            raise SystemExit("auth did not persist returned api id")
        auth_pgr = await dispatch(login_ctx, "login-user", "pgr", "")
        if "官方 RKS" not in auth_pgr.value:
            raise SystemExit(f"auth should auto-sync save for pgr, got {auth_pgr.value!r}")
        dynamic_b45 = await dispatch(login_ctx, "login-user", "b45", "")
        if "Best 45:" not in dynamic_b45.value:
            raise SystemExit(f"dynamic bN command should render requested best count, got {dynamic_b45.value!r}")
        dynamic_p12 = await dispatch(login_ctx, "login-user", "p12", "")
        if "All Perfect Top 12" not in dynamic_p12.value:
            raise SystemExit(f"dynamic pN command should route through p30 logic with requested count, got {dynamic_p12.value!r}")
        dynamic_x12 = await dispatch(login_ctx, "login-user", "x12", "")
        if "1 Good Top 12" not in dynamic_x12.value:
            raise SystemExit(f"dynamic xN command should route through x30 logic with requested count, got {dynamic_x12.value!r}")
        dynamic_fc12 = await dispatch(login_ctx, "login-user", "fc12", "")
        if "Full Combo Top 12" not in dynamic_fc12.value:
            raise SystemExit(f"dynamic fcN command should route through fc30 logic with requested count, got {dynamic_fc12.value!r}")
        set_api_token = await dispatch(login_ctx, "login-user", "setapitoken", "new-api-token")
        if "API Token 已设置为" not in set_api_token.value or login_client.set_api_token_calls[-1]["api_token"] != "new-api-token":
            raise SystemExit(f"setApiToken should submit the current user's API token, got {set_api_token.value!r}")
        token_list = await dispatch(login_ctx, "login-user", "tkls", "")
        if "已绑定 2 个平台" not in token_list.value or "（当前）" not in token_list.value or "AstrBot" not in token_list.value:
            raise SystemExit(f"tkls should list bound API platforms, got {token_list.value!r}")
        limited_list_ctx = CommandContext(
            config=PluginConfig(render_mode="text", list_score_max_num=1),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=login_ctx.store,
            client=login_client,
        )
        limited_list = await dispatch(limited_list_ctx, "login-user", "list", "")
        if "谱面数量过多" not in limited_list.value or "1" not in limited_list.value:
            raise SystemExit(f"list should reject result sets larger than list_score_max_num, got {limited_list.value!r}")
        old_achievement = await dispatch(login_ctx, "login-user", "achievement", "1 -v 100")
        if "1.0: 1/1" not in old_achievement.value or "1.5: 0/4" not in old_achievement.value:
            raise SystemExit(f"achievement -v should use oldInfo/change.csv difficulty rows, got {old_achievement.value!r}")
        b30_render_calls: list[tuple[str, dict, bool, dict | None]] = []

        async def fake_b30_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
            b30_render_calls.append((template, data, return_url, options))
            path = paths.render_cache / "fake-b30-render.png"
            Image.new("RGB", (1200, 1600), (8, 24, 50)).save(path)
            return str(path)

        image_login_ctx = CommandContext(
            config=PluginConfig(render_mode="image", render_backend="html"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=login_ctx.store,
            client=login_client,
            html_render=fake_b30_render,
        )
        image_pgr = await dispatch(image_login_ctx, "login-user", "pgr", "")
        if image_pgr.kind != "image" or not Path(image_pgr.value).exists():
            raise SystemExit(f"image pgr should render an image, got {image_pgr!r}")
        b30_template = b30_render_calls[0][0]
        b30_html = _render_call_html(b30_render_calls[0])
        if not b30_render_calls or ".b19" not in b30_template or 'class="b19"' not in b30_html:
            raise SystemExit("image pgr should render with original b19 resources")
        if not b30_render_calls[0][1]:
            raise SystemExit("image pgr should pass Jinja2 data to AstrBot")
        if "file:///" in b30_html:
            raise SystemExit("image pgr should render with self-contained HTML without local file URLs")
        if "data:image/" not in b30_html:
            raise SystemExit("image pgr should inline local image resources")
        if "themeStar()" in b30_html or "Star1" in b30_html:
            raise SystemExit("image pgr should use random blurred illustration background, not the fixed star theme")
        if "background: #000" not in b30_template or "body > :not(.background)" in b30_template:
            raise SystemExit("image pgr should set viewport reset without overriding original template positioning")
        if "position: fixed !important" in b30_template or "height: 100vh !important" in b30_template:
            raise SystemExit("image pgr background should be page-height aware, not fixed to the viewport")
        if 'background: url("") center no-repeat' not in b30_template:
            raise SystemExit("image pgr should remove original common.css phigros body fallback before t2i")
        if '<img src="data:image/' not in b30_html:
            raise SystemExit("image pgr should inline the selected illustration into the contained background layer")
        if "background: transparent !important" not in b30_template:
            raise SystemExit("image pgr should not paint the selected illustration as an unblurred body background")
        if "phigros.png" in b30_html:
            raise SystemExit("image pgr should not fall back to phigros when local illustrations exist")
        if "Real RKS:" not in b30_html:
            raise SystemExit("image pgr should include original Real RKS chip when save version is older")
        if "phiAdjustFontSize" not in b30_template:
            raise SystemExit("image pgr should include original song-name auto font sizing script")
        if "accAvg" not in b30_template or "Avg: 99.4321%" not in b30_html:
            raise SystemExit("image pgr should include original per-chart average acc status")
        if b30_render_calls[0][3] is None or b30_render_calls[0][3].get("viewport_width") != 1200:
            raise SystemExit("image pgr should receive an explicit 1200px viewport to avoid reused-context width drift")
        if b30_render_calls[0][3].get("scale") != "css":
            raise SystemExit("image pgr should use css screenshot scale so 1200 CSS pixels are not emitted as high-DPR half-cropped images")
        best_before = len(b30_render_calls)
        image_best = await dispatch(image_login_ctx, "login-user", "best", "")
        if image_best.kind != "text" or "Best 19" not in image_best.value:
            raise SystemExit(f"best should stay text-only even in image mode, got {image_best!r}")
        if len(b30_render_calls) != best_before:
            raise SystemExit("best should not call the image renderer")

        for command, css_marker, body_marker in (
            ("p30", ".b19", "All Perfect Mode"),
            ("x30", ".b19", "1 Good Mode"),
            ("fc30", ".b19", "Full Combo Mode"),
            ("info", ".Player_Info", "PLAYER_INFO"),
            ("lmtacc", ".content-box", "Limit ACC Mode"),
            ("list", ".list_box", 'class="list_box"'),
            ("lvscore", ".full-box", 'class="full-box"'),
            ("table", ".tableBox", 'class="tableBox"'),
            ("suggest", ".group_list", 'class="group_list"'),
            ("score", ".scoreHistory", "SCORE_DATA"),
            ("chap", ".song-box", 'class="song-box"'),
            ("achievement", ".tableBox", "Player Achievements"),
            ("hisb30", ".main-box", 'class="main-box"'),
            ("2025history", ".page", 'class="page"'),
            ("rand", ".box-left", 'class="box-left"'),
            ("randclg", ".tot-box", 'class="tot-box"'),
            ("song", ".big-box", 'class="big-box"'),
            ("chart", ".chart-info", "Chart Information"),
            ("jrrp", ".jrrpBkg", "今日运势"),
            ("myset", ".page-wrap", "Phi-Plugin 用户设置"),
            ("guess", ".img", 'id="phiLineArt"'),
            ("ranklist", ".list_bkg", 'class="list"'),
            ("newnotice", ".notice-page", "Smoke TapTap Notice"),
            ("newlog", "table", "新曲速递"),
        ):
            before = len(b30_render_calls)
            command_args = {
                "lmtacc": "98",
                "list": "12",
                "lvscore": "12",
                "table": "12",
                "suggest": "HD FC 1+",
                "score": "Glaciaxion -dif EZ -or score",
                "chap": "C0",
                "achievement": "12",
                "randclg": "30-45",
                "song": "Glaciaxion",
                "chart": "Glaciaxion EZ",
                "ranklist": "9",
            }.get(command, "")
            result = await dispatch(image_login_ctx, "login-user", command, command_args)
            if result.kind != "image" or not Path(result.value).exists():
                raise SystemExit(f"image {command} should render an image, got {result!r}")
            if len(b30_render_calls) != before + 1:
                raise SystemExit(f"image {command} should call the shared original html renderer")
            template = b30_render_calls[-1][0]
            html = _render_call_html(b30_render_calls[-1])
            if css_marker not in template or body_marker not in html:
                raise SystemExit(f"image {command} should render with original resources, missing {css_marker!r}/{body_marker!r}")
            if "file:///" in html or "raw.githubusercontent.com" in html:
                raise SystemExit(f"image {command} should pass self-contained HTML to remote t2i")
            if "data:image/" not in html:
                raise SystemExit(f"image {command} should inline image resources as data URIs")
            if "phiAdjustFontSize" not in template:
                raise SystemExit(f"image {command} should include shared auto font sizing script")
            if command == "score":
                if "RANK_LIST" not in html or "Selected >> EZ" not in html or "AP: 25.00%" not in html:
                    raise SystemExit("image score should render online ranklist and AP/FC statistics")
                if not login_client.score_ranklist_requests:
                    raise SystemExit("image score should request online score ranklist")
                request = login_client.score_ranklist_requests[-1]
                if request["rank"] != "EZ" or request["order_by"] != "score":
                    raise SystemExit(f"image score did not pass -dif/-or options to API: {request!r}")
                old_score_calls: list[tuple[str, dict, bool, dict | None]] = []

                async def fake_old_score_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
                    old_score_calls.append((template, data, return_url, options))
                    path = paths.render_cache / "fake-old-score-render.png"
                    Image.new("RGB", (1200, 1600), (8, 24, 50)).save(path)
                    return str(path)

                old_score_ctx = CommandContext(
                    config=PluginConfig(render_mode="image", render_backend="html", score_image_version="old"),
                    paths=paths,
                    catalog=catalog,
                    searcher=SongSearcher(catalog),
                    store=login_ctx.store,
                    client=login_client,
                    html_render=fake_old_score_render,
                )
                old_score = await dispatch(old_score_ctx, "login-user", "score", "Glaciaxion -dif EZ")
                if old_score.kind != "image" or len(old_score_calls) != 1:
                    raise SystemExit(f"old score template should render one image, got {old_score!r}")
                old_html = _render_call_html(old_score_calls[0])
                if ".playerbox" not in old_html or 'class="playerbox"' not in old_html or 'class="rank-EZ"' not in old_html:
                    raise SystemExit("old score image version should render through converted score/scoreOld")
            if command == "suggest":
                if "group-phi" not in html or "AP Count" not in html:
                    raise SystemExit("image suggest should render upstream phi/AP Count recommendation group")
                if not login_client.songs_apfc_requests:
                    raise SystemExit("image suggest should request batch AP/FC statistics")
                request = login_client.songs_apfc_requests[-1]
                if request["ranks"] != ["EZ", "HD", "IN", "AT"]:
                    raise SystemExit(f"image suggest should request all standard ranks, got {request!r}")
            if command == "info":
                options = b30_render_calls[-1][3] or {}
                if options.get("viewport_width") != 1920 or options.get("viewport_height") != 1500:
                    raise SystemExit(f"image info should use original 1920x1500 viewport, got {options!r}")
                if "--phi-viewport-width: 1920px" not in html or ".left" not in html or ".right" not in html:
                    raise SystemExit("image info should include a left/right original-layout guard")
                if "Phi-Plugin" not in html or "v0.1.0" not in html or "data-watermark-fit" in html:
                    raise SystemExit("image info should render the compact fixed watermark without adaptive scaling")
                if "(v0.1.0)" in html or '<sup class="watermark-version">v0.1.0</sup>' not in html:
                    raise SystemExit("image info watermark version should render as a superscript, not parentheses")
                if html.count("<line x1=") < 20:
                    raise SystemExit("image info should render long API history, not only the last 12 points")
                info_fetches = [item for item in login_client.history_fetches if item["user_id"] == "login-user"]
                if not info_fetches or "rks" not in (info_fetches[-1]["fields"] or []):
                    raise SystemExit(f"image info should fetch long remote history before rendering, got {info_fetches!r}")
                before_info_variant = len(b30_render_calls)
                info1 = await dispatch(image_login_ctx, "login-user", "info1", "Glaciaxion")
                if info1.kind != "image" or len(b30_render_calls) != before_info_variant + 1:
                    raise SystemExit(f"image info1 should render through the info variant route, got {info1!r}")
                info1_html = _render_call_html(b30_render_calls[-1])
                if ".Player_Info" not in info1_html or '<img src="data:image/' not in info1_html:
                    raise SystemExit("image info1 should use the current userinfo template and requested song background")
                before_info_variant = len(b30_render_calls)
                info2 = await dispatch(image_login_ctx, "login-user", "info2", "Glaciaxion")
                if info2.kind != "image" or len(b30_render_calls) != before_info_variant + 1:
                    raise SystemExit(f"image info2 should render through the old info variant route, got {info2!r}")
                info2_html = _render_call_html(b30_render_calls[-1])
                info2_options = b30_render_calls[-1][3] or {}
                if ".basis-box" not in info2_html or "Basis-Info" not in info2_html:
                    raise SystemExit("image info2 should use the original old userinfo resource chain")
                if info2_options.get("viewport_width") != 1800:
                    raise SystemExit(f"image info2 should use the old 1800px viewport, got {info2_options!r}")
            if command == "ranklist":
                options = b30_render_calls[-1][3] or {}
                if options.get("viewport_width") != 2048 or options.get("viewport_height") != 1080:
                    raise SystemExit(f"image ranklist should use original 2048x1080 viewport, got {options!r}")
                if ".b30list" not in html or "ChallengeMode History" not in html:
                    raise SystemExit("image ranklist should render the original right-side detail panel")
                old_ranklist_calls: list[tuple[str, dict, bool, dict | None]] = []

                async def fake_old_ranklist_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
                    old_ranklist_calls.append((template, data, return_url, options))
                    path = paths.render_cache / "fake-old-ranklist-render.png"
                    Image.new("RGB", (800, 1600), (8, 24, 50)).save(path)
                    return str(path)

                old_ranklist_ctx = CommandContext(
                    config=PluginConfig(render_mode="image", render_backend="html", ranklist_image_version="old"),
                    paths=paths,
                    catalog=catalog,
                    searcher=SongSearcher(catalog),
                    store=login_ctx.store,
                    client=login_client,
                    html_render=fake_old_ranklist_render,
                )
                old_ranklist = await dispatch(old_ranklist_ctx, "login-user", "ranklist", "9")
                if old_ranklist.kind != "image" or len(old_ranklist_calls) != 1:
                    raise SystemExit(f"old ranklist template should render one image, got {old_ranklist!r}")
                old_html = _render_call_html(old_ranklist_calls[0])
                old_options = old_ranklist_calls[0][3] or {}
                if old_options.get("viewport_width") != 800:
                    raise SystemExit(f"old ranklist should use its original 800px viewport, got {old_options!r}")
                if 'class="lLine' not in old_html or 'class="b19Box"' not in old_html or "总统计量" not in old_html:
                    raise SystemExit("old ranklist image version should render through converted rankingList-old template")
                if "file:///" in old_html or "raw.githubusercontent.com" in old_html:
                    raise SystemExit("old ranklist should pass self-contained HTML to remote t2i")
                if '<img src="data:image/' not in old_html:
                    raise SystemExit("old ranklist should inline image resources as data URIs")
            if command == "randclg" and ('class="notes-info tap"' not in html or ">Tap<" not in html):
                raise SystemExit("image randclg should render original tap/drag/hold/flick note breakdown")
            if command == "rand":
                options = b30_render_calls[-1][3] or {}
                if options.get("viewport_width") != 2048 or options.get("viewport_height") != 1080:
                    raise SystemExit(f"image rand should use original 2048x1080 viewport, got {options!r}")
            if command == "randclg":
                options = b30_render_calls[-1][3] or {}
                if options.get("viewport_width") != 1920 or options.get("viewport_height") != 1200:
                    raise SystemExit(f"image randclg should use original 1920x1200 viewport, got {options!r}")
            if command == "song":
                before_song_comment = len(b30_render_calls)
                song_comment = await dispatch(image_login_ctx, "login-user", "song", "Glaciaxion -comment")
                if song_comment.kind != "image" or len(b30_render_calls) != before_song_comment + 1:
                    raise SystemExit(f"image song -comment should render through atlas with comments, got {song_comment!r}")
                song_comment_html = _render_call_html(b30_render_calls[-1])
                if "comment-box" not in song_comment_html or "hello" not in song_comment_html:
                    raise SystemExit("image song -comment should render upstream atlas comment panel")
        live = await dispatch(login_ctx, "login-user", "live", "")
        if "Smoke Live" not in live.value:
            raise SystemExit(f"live should render API content, got {live.value!r}")
        empty_live_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=EmptyLiveClient(config),
        )
        empty_live = await dispatch(empty_live_ctx, "login-user", "live", "")
        if "发生错误，请稍后再试。" not in empty_live.value:
            raise SystemExit(f"live should use upstream empty-result wording, got {empty_live.value!r}")
        rankfind = await dispatch(login_ctx, "login-user", "rankfind", "12.34")
        if "12/345" not in rankfind.value or login_client.ranklist_rks_requests[-1] != 12.34:
            raise SystemExit(f"rankfind should query online rks rank, got {rankfind.value!r}")
        ranklist_text = await dispatch(login_ctx, "login-user", "ranklist", "9")
        if "RankingScore 排行榜" not in ranklist_text.value or "总数据量：345" not in ranklist_text.value:
            raise SystemExit(f"ranklist text should summarize online ranking data, got {ranklist_text.value!r}")
        if login_client.ranklist_rank_requests[-1] != 9:
            raise SystemExit(f"ranklist should pass explicit rank to API, got {login_client.ranklist_rank_requests!r}")
        comments = await dispatch(login_ctx, "login-user", "comment", "Glaciaxion")
        if "评论列表" not in comments.value or "hello" not in comments.value:
            raise SystemExit(f"comment should list song comments, got {comments.value!r}")
        add_comment = await dispatch(login_ctx, "login-user", "comment", "Glaciaxion EZ\nsmoke comment")
        if "在线评论成功" not in add_comment.value or not login_client.added_comments:
            raise SystemExit(f"comment should add online comment, got {add_comment.value!r}")
        my_comments = await dispatch(login_ctx, "login-user", "mycmt", "")
        if "您的评论列表" not in my_comments.value:
            raise SystemExit(f"mycmt should list user comments, got {my_comments.value!r}")
        delete_comment = await dispatch(login_ctx, "login-user", "recmt", "7")
        if "删除在线评论成功" not in delete_comment.value or login_client.deleted_comments != ["7"]:
            raise SystemExit(f"recmt should delete online comment, got {delete_comment.value!r}")
        tags = await dispatch(login_ctx, "login-user", "addtag", "Glaciaxion EZ")
        if "谱面标签" not in tags.value or "节奏" not in tags.value:
            raise SystemExit(f"addtag should list chart tags, got {tags.value!r}")
        set_tags = await dispatch(login_ctx, "login-user", "addtag", "Glaciaxion EZ 鑺傚 閰嶇疆")
        if "谱面标签已提交" not in set_tags.value or not login_client.set_tags:
            raise SystemExit(f"addtag should set chart tags, got {set_tags.value!r}")
        tag = await dispatch(login_ctx, "login-user", "tag", "Glaciaxion EZ")
        if "谱面标签" not in tag.value or "节奏" not in tag.value:
            raise SystemExit(f"tag should list chart tags, got {tag.value!r}")
        before_settag = len(login_client.set_tags)
        settag = await dispatch(login_ctx, "login-user", "settag", "Glaciaxion EZ 节奏 读谱")
        if "谱面标签已提交" not in settag.value or len(login_client.set_tags) != before_settag + 1:
            raise SystemExit(f"settag should set chart tags, got {settag.value!r}")
        if login_client.set_tags[-1]["tags"] != ["节奏", "读谱"]:
            raise SystemExit(f"settag should map tag names through API list, got {login_client.set_tags[-1]!r}")

        login_ctx.store.bind("bind-user", "A" * 25)
        uploads_before_bind = len(login_client.history_uploads)
        result = await dispatch(login_ctx, "bind-user", "bind", "")
        if "查询 ID: 67890" not in result.value:
            raise SystemExit(f"bind existing token expected api id, got {result.value!r}")
        if login_client.bind_calls[-1]["is_global"] is not False:
            raise SystemExit(f"bind did not apply default global flag: {login_client.bind_calls[-1]!r}")
        if len(login_client.history_uploads) <= uploads_before_bind:
            raise SystemExit("bind did not upload refreshed history")
        bind_pgr = await dispatch(login_ctx, "bind-user", "pgr", "")
        if "官方 RKS" not in bind_pgr.value:
            raise SystemExit(f"bind should auto-sync save for pgr, got {bind_pgr.value!r}")

        default_global_client = FakeLoginClient(PluginConfig(default_global=True, render_mode="text"))
        default_global_ctx = CommandContext(
            config=default_global_client.config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=default_global_client,
        )
        default_global_ctx.store.bind("gb-default-user", "E" * 25)
        await dispatch(default_global_ctx, "gb-default-user", "bind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not True:
            raise SystemExit(f"bind did not use configured global default: {default_global_client.bind_calls[-1]!r}")

        await dispatch(default_global_ctx, "gb-default-user", "cnbind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not False:
            raise SystemExit(f"cnbind did not force CN endpoint: {default_global_client.bind_calls[-1]!r}")

        await dispatch(default_global_ctx, "gb-default-user", "gbbind", "")
        if default_global_client.bind_calls[-1]["is_global"] is not True:
            raise SystemExit(f"gbbind did not force global endpoint: {default_global_client.bind_calls[-1]!r}")

        login_ctx.store.bind("api-user", "C" * 25)
        result = await dispatch(login_ctx, "api-user", "bind", "13579")
        if "查询 ID: 13579" not in result.value:
            raise SystemExit(f"bind api id expected success, got {result.value!r}")
        if login_ctx.store.get_token("api-user") is not None:
            raise SystemExit("bind api id did not clear stale token")
        api_pgr = await dispatch(login_ctx, "api-user", "pgr", "")
        if "官方 RKS" not in api_pgr.value:
            raise SystemExit(f"api id bind should auto-sync save for pgr, got {api_pgr.value!r}")

        progress_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeProgressClient(config),
        )
        progress_ctx.store.bind("progress-user", "P" * 25, api_id="999")
        first_update = await dispatch(progress_ctx, "progress-user", "update", "")
        if "进步摘要" not in first_update.value or "首次记录" not in first_update.value:
            raise SystemExit(f"first update should render progress summary, got {first_update.value!r}")
        second_update = await dispatch(progress_ctx, "progress-user", "update", "")
        if "RKS: 11.2222 (+0.1111)" not in second_update.value:
            raise SystemExit(f"second update should show rks progress, got {second_update.value!r}")
        if "Glaciaxion" not in second_update.value or "+40,000" not in second_update.value:
            raise SystemExit(f"second update should show score progress, got {second_update.value!r}")
        token_only_client = TokenOnlyProgressClient(config)
        token_only_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=token_only_client,
        )
        token_only_ctx.store.bind("token-history-user", "T" * 25)
        await dispatch(token_only_ctx, "token-history-user", "update", "")
        if not token_only_client.history_fetches or token_only_client.history_fetches[-1]["token"] != "T" * 25:
            raise SystemExit(f"token-only update should fetch long remote history with token, got {token_only_client.history_fetches!r}")
        progress_render_calls: list[tuple[str, dict, bool, dict | None]] = []

        async def fake_progress_render(template: str, data: dict, return_url: bool = True, options: dict | None = None) -> str:
            progress_render_calls.append((template, data, return_url, options))
            path = paths.render_cache / f"fake-progress-render-{len(progress_render_calls)}.png"
            Image.new("RGB", (1200, 900), (11, 29, 64)).save(path)
            return str(path)

        progress_image_ctx = CommandContext(
            config=PluginConfig(render_mode="image", render_backend="html"),
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=progress_ctx.store,
            client=FakeProgressClient(config),
            html_render=fake_progress_render,
        )
        progress_image_ctx.store.bind("progress-image-user", "P" * 25, api_id="999")
        progress_image_update = await dispatch(progress_image_ctx, "progress-image-user", "update", "")
        if progress_image_update.kind != "image" or not Path(progress_image_update.value).exists():
            raise SystemExit(f"image update should render an image, got {progress_image_update!r}")
        update_html = _render_call_html(progress_render_calls[-1])
        update_data = progress_render_calls[-1][1]
        if ".record_box" not in update_html or 'class="record_box"' not in update_html:
            raise SystemExit("image update should render through original update resources")
        if "Task_table" not in update_html:
            raise SystemExit("image update should render today's task table above history rows")
        if not update_data.get("task_data") or not any(item for item in update_data["task_data"]):
            raise SystemExit("image update should pass today's task rows into the original update template")
        if not any(line.get("color") != "#fff382" for row in update_data.get("box_line", []) for line in row):
            raise SystemExit("image update history titles should use upstream random colors, not the task-table yellow")
        if "file:///" in update_html or "raw.githubusercontent.com" in update_html:
            raise SystemExit("image update should pass self-contained HTML to remote t2i")
        if "data:image/" not in update_html:
            raise SystemExit("image update should inline image resources as data URIs")
        progress_pgr = await dispatch(progress_ctx, "progress-user", "pgr", "")
        if "官方 RKS: 11.2222" not in progress_pgr.value:
            raise SystemExit(f"update should refresh pgr cache, got {progress_pgr.value!r}")
        progress_chap = await dispatch(progress_ctx, "progress-user", "chap", "C0")
        if "章节成绩：Chapter Legacy 过去的章节" not in progress_chap.value or "Glaciaxion" not in progress_chap.value:
            raise SystemExit(f"chap should render chapter score summary, got {progress_chap.value!r}")
        progress_achievement = await dispatch(progress_ctx, "progress-user", "achievement", "1")
        if "Player Achievements 1.0-1.9" not in progress_achievement.value:
            raise SystemExit(f"achievement should render difficulty rows, got {progress_achievement.value!r}")
        progress_hisb30 = await dispatch(progress_ctx, "progress-user", "hisb30", "")
        if "历史 B30 变化" not in progress_hisb30.value or "Glaciaxion" not in progress_hisb30.value:
            raise SystemExit(f"hisb30 should render history changes, got {progress_hisb30.value!r}")
        progress_history = await dispatch(progress_ctx, "progress-user", "2025history", "")
        if "年度历史总结" not in progress_history.value or "历史成绩记录" not in progress_history.value:
            raise SystemExit(f"2025history should render history summary, got {progress_history.value!r}")

        nick_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
            is_admin=True,
        )
        setnick = await dispatch(nick_ctx, "admin-user", "setnick", "Glaciaxion ---> codex-smoke-alias-98765")
        if "设置完成" not in setnick.value:
            raise SystemExit(f"setnick should persist alias, got {setnick.value!r}")
        alias_hit = nick_ctx.searcher.best("codex-smoke-alias-98765")
        if alias_hit is None or alias_hit.title != "Glaciaxion":
            raise SystemExit("setnick did not update in-memory search aliases")
        delnick = await dispatch(nick_ctx, "admin-user", "delnick", "Glaciaxion ---> codex-smoke-alias-98765")
        if "删除完成" not in delnick.value:
            raise SystemExit(f"delnick should remove custom alias, got {delnick.value!r}")
        alias_removed = nick_ctx.searcher.best("codex-smoke-alias-98765")
        if alias_removed is not None and alias_removed.title == "Glaciaxion":
            raise SystemExit("delnick did not update in-memory search aliases")
        non_admin_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=PhiApiClient(config),
        )
        denied = await dispatch(non_admin_ctx, "normal-user", "setnick", "Glaciaxion ---> test")
        if "只有管理员" not in denied.value:
            raise SystemExit(f"setnick should require admin, got {denied.value!r}")
        denied_delnick = await dispatch(non_admin_ctx, "normal-user", "delnick", "Glaciaxion ---> test")
        if "只有管理员" not in denied_delnick.value:
            raise SystemExit(f"delnick should require admin, got {denied_delnick.value!r}")

        sent: list[CommandResult] = []

        async def capture(result: CommandResult) -> None:
            sent.append(result)

        taptap = FakeTapTapLogin(config, paths)
        qrcode_ctx = CommandContext(
            config=config,
            paths=paths,
            catalog=catalog,
            searcher=SongSearcher(catalog),
            store=SaveStore(paths.data_dir),
            client=FakeLoginClient(config),
            taptap=taptap,
            sender=capture,
        )
        result = await dispatch(qrcode_ctx, "qr-user", "bind", "qrcode")
        if "TapTap 二维码登录已完成" not in result.value:
            raise SystemExit(f"qrcode bind expected completion, got {result.value!r}")
        if qrcode_ctx.store.get_token("qr-user") != "D" * 25:
            raise SystemExit("qrcode bind did not persist returned sessionToken")
        qr_pgr = await dispatch(qrcode_ctx, "qr-user", "pgr", "")
        if "官方 RKS" not in qr_pgr.value:
            raise SystemExit(f"qrcode bind should auto-sync save for pgr, got {qr_pgr.value!r}")
        if len(sent) != 3 or sent[0].kind != "image" or sent[1].kind != "text" or sent[2].kind != "text":
            raise SystemExit(f"qrcode bind did not emit qr image, hint, and scanned notice: {sent!r}")
        if "二维码已扫描" not in sent[2].value:
            raise SystemExit(f"qrcode bind did not emit scanned notice: {sent!r}")
        if taptap.request_use_global is not False or taptap.wait_use_global is not False:
            raise SystemExit(f"qrcode bind did not use default endpoint: {taptap.request_use_global}, {taptap.wait_use_global}")
        if not Path(sent[0].value).exists():
            raise SystemExit("qrcode image was not created")

        print("dispatch smoke passed")
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
