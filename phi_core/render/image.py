from __future__ import annotations

import html
import re
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..paths import PluginPaths

WIDTH = 1200
MARGIN_X = 72
CARD_GAP = 14
CARD_WIDTH = (WIDTH - MARGIN_X * 2 - CARD_GAP * 2) // 3
CARD_HEIGHT = 140

HELP_GROUPS = [
    {
        "group": "账号与存档",
        "items": [
            ("phi bind <sessionToken|查询ID>", "绑定 token 或查询平台 ID"),
            ("phi auth <API Token>", "使用查询平台 API Token 登录并保存 sessionToken"),
            ("phi update", "更新存档并查看进步情况"),
            ("phi unbind", "解绑并清理缓存"),
            ("phi id", "查看查询 ID / PlayerId"),
            ("phi sessiontoken", "查看本地 token 脱敏信息"),
        ],
    },
    {
        "group": "曲目查询",
        "items": [
            ("phi song <曲名/别名>", "查询曲目信息、难度、曲师与画师"),
            ("phi search <关键词>", "搜索曲目与别名"),
            ("phi rand", "随机抽取一首曲目"),
            ("phi ill <曲名/别名>", "发送本地曲绘"),
            ("phi down ill", "下载或更新原版曲绘资源"),
            ("phi alias <曲名/别名>", "查询本地别名库"),
            ("phi tips / newlog", "随机 Tips 或查看本地更新日志"),
        ],
    },
    {
        "group": "成绩统计",
        "items": [
            ("phi b30 / phi rks / phi pgr", "基于缓存存档输出 B30/RKS"),
            ("phi score <曲名/别名>", "查询单曲成绩"),
            ("phi info", "查询个人统计摘要"),
            ("phi data", "查询 Data 数量"),
            ("phi best [数量]", "文本版 Best 成绩列表"),
            ("phi p30/fc30/x30", "AP、FC、1 Good 模式列表"),
            ("phi lmtacc <acc>", "限制最低 ACC 后重算列表"),
            ("phi list [条件]", "按定数、ACC、评级筛选成绩"),
            ("phi lvscore [条件]", "统计指定定数/难度范围成绩"),
            ("phi suggest", "基于缓存成绩估算推分建议"),
            ("phi randclg [范围]", "随机三曲课题"),
            ("phi table <定数>", "查询本地定数表"),
            ("phi chap <章节|all>", "查询章节成绩概览"),
            ("phi achievement <定数>", "查询定数成就概览"),
            ("phi hisb30 / 2025history", "查看历史 B30 与年度总结"),
            ("phi live / cmt / addtag", "直播速递、在线评论、谱面标签"),
        ],
    },
    {
        "group": "本地管理",
        "items": [
            ("phi setnick 原名 ---> 别名", "管理员添加本地曲目别名"),
        ],
    },
    {
        "group": "迁移状态",
        "items": [
            ("phi help", "查看帮助与当前迁移范围"),
            ("暂未迁移", "小游戏、签到任务、排行榜、管理命令、部分原版图片模板"),
        ],
    },
]


def render_help_panel(paths: PluginPaths) -> Path:
    title_font = _font(paths, 64, title=True)
    group_font = _font(paths, 42)
    command_font = _font(paths, 22)
    desc_font = _font(paths, 18)
    footer_font = _font(paths, 24, title=True)

    group_height = 82
    footer_height = 130
    height = 150 + footer_height
    for group in HELP_GROUPS:
        rows = (len(group["items"]) + 2) // 3
        height += group_height + rows * (CARD_HEIGHT + CARD_GAP) + 26

    image = _base_image(paths, height)
    draw = ImageDraw.Draw(image, "RGBA")

    y = 54
    _draw_centered_text(draw, (0, y, WIDTH, y + 76), "Phi Plugin Query Core", title_font, (255, 255, 255, 255))
    y += 108

    for group in HELP_GROUPS:
        _rounded_box(draw, (MARGIN_X, y, WIDTH - MARGIN_X, y + group_height), (58, 149, 220, 108), radius=20)
        _draw_centered_text(draw, (MARGIN_X, y, WIDTH - MARGIN_X, y + group_height), f"——·{group['group']}·——", group_font, (255, 255, 255, 255))
        y += group_height + 16

        for index, (command, desc) in enumerate(group["items"]):
            col = index % 3
            row = index // 3
            x = MARGIN_X + col * (CARD_WIDTH + CARD_GAP)
            top = y + row * (CARD_HEIGHT + CARD_GAP)
            _draw_help_card(draw, (x, top, x + CARD_WIDTH, top + CARD_HEIGHT), command, desc, command_font, desc_font)
        y += ((len(group["items"]) + 2) // 3) * (CARD_HEIGHT + CARD_GAP) + 28

    _draw_centered_text(draw, (0, height - 108, WIDTH, height - 66), "AstrBot Phi Plugin", footer_font, (255, 255, 255, 255))
    _draw_centered_text(draw, (0, height - 70, WIDTH, height - 40), "Created with native Python renderer", _font(paths, 18), (218, 239, 255, 230))
    return _save(paths, image, "help")


def render_text_panel(paths: PluginPaths, text: str, title: str = "Phi Plugin") -> Path:
    title_font = _font(paths, 52, title=True)
    body_font = _font(paths, 28)
    small_font = _font(paths, 20)

    lines = _wrap_multiline(text, body_font, WIDTH - MARGIN_X * 2 - 64)
    line_height = 40
    height = max(360, 172 + len(lines) * line_height + 110)

    image = _base_image(paths, height)
    draw = ImageDraw.Draw(image, "RGBA")
    _draw_centered_text(draw, (0, 46, WIDTH, 110), title, title_font, (255, 255, 255, 255))

    box = (MARGIN_X, 142, WIDTH - MARGIN_X, height - 82)
    _rounded_box(draw, box, (19, 69, 118, 168), radius=24)
    _rounded_box(draw, (box[0] + 10, box[1] + 10, box[2] - 10, box[3] - 10), (95, 189, 239, 58), radius=18)

    y = box[1] + 34
    for line in lines:
        draw.text((box[0] + 36, y), line, font=body_font, fill=(255, 255, 255, 245))
        y += line_height

    _draw_centered_text(draw, (0, height - 64, WIDTH, height - 30), "Phi Plugin", small_font, (218, 239, 255, 220))
    return _save(paths, image, "panel")


def _draw_help_card(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    command: str,
    desc: str,
    command_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    desc_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = rect
    _rounded_box(draw, rect, (26, 112, 185, 116), radius=14)

    left = x1 + int((x2 - x1) * 0.38)
    draw.polygon([(x1, y1), (left + 16, y1), (left - 10, y2), (x1, y2)], fill=(126, 207, 242, 116))
    draw.polygon([(left - 8, y1), (x2, y1), (x2, y2), (left - 34, y2)], fill=(65, 156, 220, 126))
    draw.rectangle((x1, y1, x2, y1 + 2), fill=(185, 234, 255, 130))

    command_lines = _wrap_command(command, command_font, left - x1 - 28)
    command_text = "\n".join(command_lines[:3])
    command_bbox = draw.multiline_textbbox((0, 0), command_text, font=command_font, spacing=4)
    command_h = command_bbox[3] - command_bbox[1]
    draw.multiline_text(
        (x1 + 14, y1 + (CARD_HEIGHT - command_h) / 2),
        command_text,
        font=command_font,
        fill=(255, 255, 255, 255),
        spacing=4,
        align="center",
    )

    desc = _plain(desc)
    desc_lines = _wrap_multiline(desc, desc_font, x2 - left - 38)
    y = y1 + 22
    for line in desc_lines[:4]:
        draw.text((left + 12, y), line, font=desc_font, fill=(255, 255, 255, 235))
        y += 25


def _base_image(paths: PluginPaths, height: int) -> Image.Image:
    background = _background(paths, height)
    overlay = Image.new("RGBA", (WIDTH, height), (8, 26, 50, 126))
    image = Image.alpha_composite(background.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, WIDTH, height), fill=(7, 23, 45, 72))
    for y in range(0, height, 26):
        alpha = 26 if y % 52 == 0 else 12
        draw.line((0, y, WIDTH, y), fill=(154, 220, 255, alpha), width=1)
    return image


def _background(paths: PluginPaths, height: int) -> Image.Image:
    candidates = list(paths.other_ill.glob("*.png")) + list(paths.other_ill.glob("*.jpg"))
    if not candidates:
        return _gradient(height)
    try:
        source = Image.open(candidates[0]).convert("RGB")
    except OSError:
        return _gradient(height)

    ratio = max(WIDTH / source.width, height / source.height)
    resized = source.resize((int(source.width * ratio), int(source.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - WIDTH) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + WIDTH, top + height)).filter(ImageFilter.GaussianBlur(18))


def _gradient(height: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, height), (8, 24, 50))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(8 + 20 * t),
            int(24 + 64 * t),
            int(50 + 110 * t),
        )
        draw.line((0, y, WIDTH, y), fill=color)
    return image


def font_diagnostics(paths: PluginPaths) -> list[str]:
    return [str(path) for path in _font_candidates(paths, title=False)]


def selected_font_path(paths: PluginPaths, *, title: bool = False) -> str:
    font = _font(paths, 24, title=title)
    return str(getattr(font, "path", "(Pillow default font)"))


def _font(paths: PluginPaths, size: int, *, title: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _font_candidates(paths, title=title):
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _font_candidates(paths: PluginPaths, *, title: bool) -> list[Path]:
    font_dir = paths.resources / "fonts"
    candidates = []
    if title:
        candidates.append(font_dir / "Aldrich-Regular.ttf")
    candidates.extend([
        font_dir / "NotoSansSC-VF.ttf",
        font_dir / "NotoSansSC-Regular.otf",
        font_dir / "SourceHanSansSC-Regular.otf",
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyh.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        font_dir / "NotoSansJP.ttf",
        font_dir / "Aldrich-Regular.ttf",
    ])
    return candidates


def _wrap_multiline(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    for paragraph in _plain(text).splitlines() or [""]:
        lines.extend(_wrap_line(draw, paragraph, font, max_width))
    return lines


def _wrap_command(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text]

    chunks = re.split(r"(\s+|/)", text)
    lines: list[str] = []
    current = ""
    for chunk in chunks:
        if not chunk:
            continue
        trial = current + chunk
        if draw.textbbox((0, 0), trial.strip(), font=font)[2] <= max_width:
            current = trial
            continue
        if current.strip():
            lines.append(current.strip())
        current = chunk
    if current.strip():
        lines.append(current.strip())

    fixed: list[str] = []
    for line in lines:
        if draw.textbbox((0, 0), line, font=font)[2] <= max_width:
            fixed.append(line)
        else:
            fixed.extend(_wrap_line(draw, line, font, max_width))
    return fixed


def _wrap_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def _plain(value: str) -> str:
    text = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = rect
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - width) / 2, y1 + (y2 - y1 - height) / 2 - 4), text, font=font, fill=fill)


def _rounded_box(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], fill: tuple[int, int, int, int], radius: int) -> None:
    draw.rounded_rectangle(rect, radius=radius, fill=fill, outline=(180, 235, 255, 82), width=2)


def _save(paths: PluginPaths, image: Image.Image, name: str) -> Path:
    paths.render_cache.mkdir(parents=True, exist_ok=True)
    path = paths.render_cache / f"{name}-{uuid.uuid4().hex[:10]}.png"
    image.convert("RGB").save(path, "PNG", optimize=True)
    return path
