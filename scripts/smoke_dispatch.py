from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_RESOURCES = ROOT.parent / "phi-plugin" / "resources"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.commands import CommandContext, ROUTE_MODULES, dispatch
from phi_core.config import PluginConfig
from phi_core.data.illustrations import find_background_illustration_file, random_background_source
from phi_core.data import SongSearcher, load_catalog
from phi_core.models import Best30Result, SaveSnapshot, ScoreRecord
from phi_core.paths import PluginPaths
from phi_core.render import html_renderer, original, panel
from phi_core.save import ApiBindResult, PgrTokenResult, PhiApiClient, SaveStore, TapTapLoginResult, TapTapQrLogin, TapTapQrRequest
from phi_core.save.taptap import _is_oauth_waiting_response


class FakeLoginClient(PhiApiClient):
    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.bind_calls: list[dict[str, object | None]] = []
        self.save_counter = 0
        self.history_uploads: list[dict] = []
        self.added_comments: list[dict] = []
        self.deleted_comments: list[str] = []
        self.set_tags: list[dict] = []

    async def bind_user(self, user_id: str, *, token=None, api_id=None, is_global=None):  # type: ignore[override]
        self.bind_calls.append({"user_id": user_id, "token": token, "api_id": api_id, "is_global": is_global})
        return ApiBindResult(api_id=str(api_id or "67890"), have_api_token=False)

    async def get_pgr_token(self, user_id: str, api_token: str):  # type: ignore[override]
        return PgrTokenResult(token="B" * 25, api_id="24680")

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
        return {}

    async def set_history(self, user_id: str, history: dict, *, token=None, api_id=None):  # type: ignore[override]
        self.history_uploads.append(history)

    async def live_info(self):  # type: ignore[override]
        return "Smoke Live"

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

    async def set_chart_tags(self, user_id: str, *, token=None, api_id=None, song_id: str, rank: str, tags: list[str]):  # type: ignore[override]
        self.set_tags.append({"song_id": song_id, "rank": rank, "tags": tags})


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
        self.saves = [
            sample_save(rks=11.1111, score=930000, acc=96.5, modified="2026-05-29T13:00:00+00:00"),
            sample_save(rks=11.2222, score=970000, acc=99.1, modified="2026-05-29T14:00:00+00:00"),
        ]

    async def fetch_cloud_save(self, token=None, user_id=None, api_id=None):  # type: ignore[override]
        if len(self.saves) > 1:
            return self.saves.pop(0)
        return self.saves[0]

    async def fetch_history(self, user_id: str, *, token=None, api_id=None, fields=None):  # type: ignore[override]
        return {}

    async def set_history(self, user_id: str, history: dict, *, token=None, api_id=None):  # type: ignore[override]
        return None


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
    for name in ("html", "info", "otherill"):
        shutil.copytree(UPSTREAM_RESOURCES / name, paths.downloads / name, dirs_exist_ok=True)


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
            for index in range(33)
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
            original._remote_image_data_uri = lambda _paths, _url: ""
            online_help_html = original.help_html(online_paths)
        finally:
            original._remote_image_data_uri = original_remote_loader
        if "raw.githubusercontent.com/Catrong/phi-plugin-ill/main/illBlur/" not in online_help_html:
            raise SystemExit("html background should keep online illustration URL when local prefetch fails")
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
            ("pgr", "", "还没有可用"),
            ("data", "", "还没有可用"),
            ("id", "", "查询 ID: 12345"),
            ("sessiontoken", "", "AAAA"),
            ("auth", "", "请提供查询平台 API Token"),
            ("best", "", "还没有可用"),
            ("tips", "", ""),
            ("alias", "Glaciaxion", "name: Glaciaxion"),
            ("com", "15.0 99.5", "等效 RKS"),
            ("table", "15", "定数表 15"),
            ("newnotice", "", "更新公告"),
            ("newlog", "", "最新版本"),
            ("randclg", "30-45", "随机课题"),
            ("down", "bad", "格式：phi down resources"),
        ]
        for command, args, expected in cases:
            result = await dispatch(ctx, "smoke-user", command, args)
            if expected and expected not in result.value:
                raise SystemExit(f"{command} expected {expected!r}, got {result.value!r}")
            first_line = result.value.splitlines()[0]
            safe_line = first_line.encode("utf-8", errors="backslashreplace").decode("utf-8")
            print(f"{command}: {safe_line}")

        if ROUTE_MODULES.get("pgr") != "pgr":
            raise SystemExit(f"pgr route mismatch: {ROUTE_MODULES.get('pgr')}")

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
        if not html_render_calls or 'class="help_box"' not in html_render_calls[0][0] or ".help_box" not in html_render_calls[0][0]:
            raise SystemExit("official html renderer was not called with the original help resources")
        if "file:///" in html_render_calls[0][0]:
            raise SystemExit("official html renderer should receive self-contained help HTML without local file URLs")
        if "data:image/" not in html_render_calls[0][0]:
            raise SystemExit("official html renderer should inline local help images as data URIs")
        if "themeStar()" in html_render_calls[0][0]:
            raise SystemExit("help html should use random blurred illustration background, not the fixed star theme")
        if "phiAdjustFontSize" not in html_render_calls[0][0]:
            raise SystemExit("official html renderer should include original auto font sizing script")
        if html_render_calls[0][2] is not False:
            raise SystemExit("official html renderer should return a local file path")
        if html_render_calls[0][1] != {}:
            raise SystemExit("official html renderer should receive pre-rendered HTML with an empty data dict")
        if "@font-face" not in html_render_calls[0][0]:
            raise SystemExit("official html renderer should receive inlined original common css resources")
        if html_render_calls[0][3] is None or html_render_calls[0][3].get("type") != "png":
            raise SystemExit("official html renderer should be asked for png output")

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
        if not b30_render_calls or ".b19" not in b30_render_calls[0][0] or 'class="b19"' not in b30_render_calls[0][0]:
            raise SystemExit("image pgr should render with original b19 resources")
        if "file:///" in b30_render_calls[0][0]:
            raise SystemExit("image pgr should render with self-contained HTML without local file URLs")
        if "data:image/" not in b30_render_calls[0][0]:
            raise SystemExit("image pgr should inline local image resources")
        if "themeStar()" in b30_render_calls[0][0] or "Star1" in b30_render_calls[0][0]:
            raise SystemExit("image pgr should use random blurred illustration background, not the fixed star theme")
        if "phigros.png" in b30_render_calls[0][0]:
            raise SystemExit("image pgr should not fall back to phigros when local illustrations exist")
        if "Real RKS:" not in b30_render_calls[0][0]:
            raise SystemExit("image pgr should include original Real RKS chip when save version is older")
        if "phiAdjustFontSize" not in b30_render_calls[0][0]:
            raise SystemExit("image pgr should include original song-name auto font sizing script")
        if "accAvg" not in b30_render_calls[0][0] or "Avg: 99.4321%" not in b30_render_calls[0][0]:
            raise SystemExit("image pgr should include original per-chart average acc status")
        live = await dispatch(login_ctx, "login-user", "live", "")
        if "Smoke Live" not in live.value:
            raise SystemExit(f"live should render API content, got {live.value!r}")
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
        set_tags = await dispatch(login_ctx, "login-user", "addtag", "Glaciaxion EZ 节奏 配置")
        if "谱面标签已提交" not in set_tags.value or not login_client.set_tags:
            raise SystemExit(f"addtag should set chart tags, got {set_tags.value!r}")

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
        setnick = await dispatch(nick_ctx, "admin-user", "setnick", "Glaciaxion ---> 烟花冰川")
        if "设置完成" not in setnick.value:
            raise SystemExit(f"setnick should persist alias, got {setnick.value!r}")
        alias_hit = nick_ctx.searcher.best("烟花冰川")
        if alias_hit is None or alias_hit.title != "Glaciaxion":
            raise SystemExit("setnick did not update in-memory search aliases")
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
