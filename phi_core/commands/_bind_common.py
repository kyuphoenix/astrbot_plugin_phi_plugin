from __future__ import annotations

from .common import CommandContext, CommandResult
from ..render import text as render
from ..save import SaveNotAvailable, StoreError


async def bind_account(
    ctx: CommandContext,
    user_id: str,
    args: str,
    *,
    is_global: bool | None = None,
) -> CommandResult:
    account = args.strip().split()[0] if args.strip() else ""
    if not account:
        token = ctx.store.get_token(user_id)
        if token:
            return await _bind_token(ctx, user_id, token, is_global=_resolve_global(ctx, is_global))
        return CommandResult.text(render.render_bind_need_account())
    if account.casefold() == "qrcode":
        return await _bind_qrcode(ctx, user_id, is_global=is_global)

    if ctx.store.validate_token(account):
        return await _bind_token(ctx, user_id, account, is_global=_resolve_global(ctx, is_global))
    if ctx.store.validate_api_id(account):
        return await _bind_api_id(ctx, user_id, account)
    return await _bind_token(ctx, user_id, account, is_global=_resolve_global(ctx, is_global))


async def _bind_api_id(ctx: CommandContext, user_id: str, api_id: str) -> CommandResult:
    try:
        old_api_id = ctx.store.get_api_id(user_id)
        bind_result = await ctx.client.bind_user(user_id, api_id=api_id)
        ctx.store.set_api_id(user_id, bind_result.api_id)
        ctx.store.clear_token(user_id)
        if old_api_id != bind_result.api_id:
            ctx.store.clear_snapshot(user_id)
        return CommandResult.text(render.render_bind_ok(api_id=bind_result.api_id))
    except (SaveNotAvailable, StoreError) as exc:
        return CommandResult.text(f"绑定查询 ID 失败：{exc}")


async def _bind_qrcode(ctx: CommandContext, user_id: str, *, is_global: bool | None = None) -> CommandResult:
    if ctx.taptap is None:
        return CommandResult.text(render.render_qrcode_not_available())
    resolved_global = _resolve_global(ctx, is_global)
    try:
        request = await ctx.taptap.request_qrcode(use_global=resolved_global)
        qr_path = ctx.taptap.render_qrcode(request)
        region = "国际服" if resolved_global else "国服"
        scan_hint = (
            f"请使用 TapTap 扫描二维码并确认登录（{region}）。"
            f"\n二维码链接剩余时间：{request.expires_in}s"
            "\n请勿错扫他人二维码；请只在信任 Bot 来源时扫码。"
            f"\n\n{request.qrcode_url}"
        )
        if ctx.sender is not None:
            await ctx.sender(CommandResult.image(qr_path))
            await ctx.sender(CommandResult.text(scan_hint))
        else:
            return CommandResult.image(qr_path)
        login = await ctx.taptap.wait_for_session_token(
            request,
            use_global=resolved_global,
            on_scanned=lambda: ctx.sender(CommandResult.text("二维码已扫描，请在 TapTap 中确认登录。")) if ctx.sender else None,
        )
        bind_result = await _bind_token(ctx, user_id, login.session_token, is_global=resolved_global)
        if isinstance(bind_result.value, str) and "绑定成功" in bind_result.value:
            bind_result.value = bind_result.value + "\n" + "TapTap 二维码登录已完成。"
        return bind_result
    except SaveNotAvailable as exc:
        return CommandResult.text(f"TapTap 二维码登录失败：{exc}")


def _resolve_global(ctx: CommandContext, is_global: bool | None) -> bool:
    return ctx.config.default_global if is_global is None else bool(is_global)


async def _bind_token(
    ctx: CommandContext,
    user_id: str,
    token: str,
    *,
    is_global: bool | None = None,
) -> CommandResult:
    old_token = ctx.store.get_token(user_id)
    try:
        ctx.store.bind(user_id, token)
        if old_token != token:
            ctx.store.clear_api_id(user_id)
            ctx.store.clear_snapshot(user_id)
    except StoreError as exc:
        return CommandResult.text(str(exc))

    try:
        bind_result = await ctx.client.bind_user(user_id, token=token, is_global=is_global)
        ctx.store.set_api_id(user_id, bind_result.api_id)
        warning = ""
        if bind_result.have_api_token is False:
            warning = "查询平台尚未记录 API Token；基础查分可继续使用，后续高级 API 功能可能需要补充。"
        return CommandResult.text(render.render_bind_ok(api_id=bind_result.api_id, warning=warning))
    except SaveNotAvailable as exc:
        warning = f"本地 token 已保存，但查询 API 登录失败：{exc}"
        return CommandResult.text(render.render_bind_ok(warning=warning))
    except StoreError as exc:
        warning = f"本地 token 已保存，但查询 ID 保存失败：{exc}"
        return CommandResult.text(render.render_bind_ok(warning=warning))
