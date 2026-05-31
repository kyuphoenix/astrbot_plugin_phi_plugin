from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from .common import CommandContext, CommandResult
from ._rendering import render_jinja_template
from ..models import Song
from ..render import jinja_adapter, original
from ..render import text as render

try:
    from pypinyin import Style, lazy_pinyin
except Exception:  # pragma: no cover - optional runtime dependency fallback
    Style = None
    lazy_pinyin = None

GameKind = Literal["guess_ill", "tip_game", "letter_game"]

IMAGE_WIDTH = 2048
IMAGE_HEIGHT = 1080
DEFAULT_LETTER_NUM = 8
DEFAULT_TIP_NUM = 8


@dataclass(slots=True)
class GuessImageData:
    illustration: str
    width: int
    height: int
    x: int
    y: int
    blur: int = 0
    saturate: float = 1.0
    invert: bool = False
    hue_rotate: int = 0
    line_mode: bool = False
    style: int = 0
    ans: str = ""
    chosen_interferences: list[str] = field(default_factory=list)

    @property
    def filter_style(self) -> str:
        filters: list[str] = []
        if self.line_mode:
            filters.append("url(#phiLineArt)")
        else:
            if self.saturate != 1:
                filters.append(f"saturate({self.saturate:g})")
            if self.invert:
                filters.append("invert(1)")
            if self.hue_rotate:
                filters.append(f"hue-rotate({self.hue_rotate}deg)")
        if self.blur > 0:
            filters.append(f"blur({self.blur}px)")
        return f"filter: {' '.join(filters)};" if filters else ""

    def to_template(self) -> dict[str, Any]:
        return {
            "illustration": self.illustration,
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
            "blur": self.blur,
            "saturate": self.saturate,
            "invert": self.invert,
            "hueRotate": self.hue_rotate,
            "lineMode": self.line_mode,
            "style": self.style,
            "ans": self.ans,
            "filterStyle": self.filter_style,
            "chosenInterferences": list(self.chosen_interferences),
        }


@dataclass(slots=True)
class GuessIllGame:
    song_id: str
    image: GuessImageData
    known_info: dict[str, str] = field(default_factory=dict)
    remaining_info: list[str] = field(default_factory=lambda: ["chapter", "bpm", "composer", "length", "illustrator", "chart"])
    actions: list[int] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    kind: GameKind = "guess_ill"


@dataclass(slots=True)
class TipGame:
    song_id: str
    tips: list[str]
    image: GuessImageData
    tip_count: int = 1
    started_at: float = field(default_factory=time.time)

    kind: GameKind = "tip_game"


@dataclass(slots=True)
class LetterGame:
    song_ids: list[str]
    song_titles: list[str]
    hidden_titles: list[str | None]
    winners: list[str]
    opened: list[str] = field(default_factory=list)
    selected_range: str = "pgr"
    started_at: float = field(default_factory=time.time)

    kind: GameKind = "letter_game"


GameState = GuessIllGame | TipGame | LetterGame

_ACTIVE_GAMES: dict[str, GameState] = {}
_ILL_WEIGHTS: dict[str, dict[str, float]] = {}
_LETTER_WEIGHTS: dict[str, dict[str, float]] = {}


async def handle_guess(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    state = _current_game(ctx, user_id)
    if args.strip():
        if state is None:
            return CommandResult.text("当前没有正在进行的猜歌游戏。发送 phi guess 可以开始猜曲绘。")
        if isinstance(state, (GuessIllGame, TipGame)):
            return await _guess_song_answer(ctx, user_id, args.strip(), state)
        return CommandResult.text("当前正在进行开字母猜歌，请使用 phi ltr n1 <曲名> 回答指定编号。")
    if state is not None:
        return CommandResult.text("当前存在未结束的游戏。请先使用 phi ans 结束，或继续回答当前游戏。")
    return await _start_guess_ill(ctx, user_id)


async def handle_tipgame(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if args.strip() and isinstance(_current_game(ctx, user_id), TipGame):
        return await handle_guess(ctx, user_id, args)
    if _current_game(ctx, user_id) is not None:
        return CommandResult.text("当前存在未结束的游戏。请先使用 phi ans 结束当前游戏。")
    return _start_tip_game(ctx, user_id)


async def handle_letter(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    state = _current_game(ctx, user_id)
    text = args.strip()
    if isinstance(state, LetterGame):
        if text:
            return _guess_letter_answer(ctx, user_id, state, text)
        return CommandResult.text(_letter_puzzle_text(state))
    if state is not None:
        return CommandResult.text("当前存在未结束的其他猜歌游戏。请先使用 phi ans 结束当前游戏。")
    return _start_letter_game(ctx, user_id, text)


async def handle_tip(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    state = _current_game(ctx, user_id)
    if state is None:
        return CommandResult.text("当前没有正在进行的游戏。可使用 phi guess / phi tipgame / phi ltr 开始。")
    if isinstance(state, GuessIllGame):
        return await _guess_ill_tip(ctx, user_id, state)
    if isinstance(state, TipGame):
        return await _tip_game_next(ctx, user_id, state)
    return _letter_tip(ctx, user_id, state)


async def handle_ans(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    key = _session_key(ctx, user_id)
    state = _ACTIVE_GAMES.get(key)
    if state is None:
        return CommandResult.text("当前没有正在进行的游戏。")
    song = _state_song(ctx, state)
    if song is None:
        _ACTIVE_GAMES.pop(key, None)
        return CommandResult.text("游戏数据已失效，已结束当前游戏。")
    _ACTIVE_GAMES.pop(key, None)
    if isinstance(state, LetterGame):
        return CommandResult.text("好吧，公布答案：\n" + _letter_answer_text(state))
    return await _finish_with_answer(ctx, "好吧，下面公布答案。", song, state)


async def handle_open(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    state = _current_game(ctx, user_id)
    if not isinstance(state, LetterGame):
        return CommandResult.text("当前没有正在进行的开字母猜歌。发送 phi ltr 可以开始。")
    letter = args.strip()
    if not letter:
        return CommandResult.text("请指定要翻开的字符，例如：phi open A")
    return _letter_open(ctx, user_id, state, letter[0])


async def _start_guess_ill(ctx: CommandContext, user_id: str) -> CommandResult:
    key = _session_key(ctx, user_id)
    song = _weighted_song(ctx, key, _ILL_WEIGHTS, _songs_with_illustrations(ctx), decay=0.4)
    if song is None:
        return CommandResult.text("当前曲库没有可用于猜曲绘的本地曲绘资源，请先执行 phi down ill 下载曲绘。")
    image = _new_guess_image(ctx, song, crop_min=100, crop_max=140)
    level = _weighted_choice([(1, 5), (2, 3), (3, 2)])
    _apply_initial_interference(image, level)
    actions = [0, 1, 2, 3]
    if image.blur <= 0:
        actions.remove(1)
    if _has_non_blur_interference(image):
        actions.append(4)
    state = GuessIllGame(song_id=song.id, image=image, actions=actions)
    _ACTIVE_GAMES[key] = state
    message = "\n".join(
        [
            "下面开始进行猜曲绘！",
            "请使用 phi guess <曲名> 回答；phi tip 获取提示；phi ans 公布答案。",
            f"本局难度：{level}；干扰类型：{'、'.join(image.chosen_interferences) or '无'}",
        ]
    )
    return await _image_game_result(ctx, message, image, "guess")


def _start_tip_game(ctx: CommandContext, user_id: str) -> CommandResult:
    key = _session_key(ctx, user_id)
    song = _weighted_song(ctx, key, _ILL_WEIGHTS, _songs_with_illustrations(ctx), decay=0.6)
    if song is None:
        return CommandResult.text("当前曲库没有可用于提示猜歌的本地曲绘资源，请先执行 phi down ill 下载曲绘。")
    tips = _song_tips(song)
    random.shuffle(tips)
    tips = tips[:DEFAULT_TIP_NUM]
    image = _new_guess_image(ctx, song, crop_min=100, crop_max=150)
    _ACTIVE_GAMES[key] = TipGame(song_id=song.id, tips=tips, image=image)
    return CommandResult.text(
        "下面开始进行提示猜歌！请使用 phi guess <曲名> 回答，phi tip 获取下一条提示，phi ans 公布答案。\n\n"
        + _tip_list(tips, 1)
    )


def _start_letter_game(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    key = _session_key(ctx, user_id)
    pool, label = _letter_pool(ctx, args)
    if len(pool) < DEFAULT_LETTER_NUM:
        return CommandResult.text(f"可用曲目不足 {DEFAULT_LETTER_NUM} 首，无法开始开字母猜歌。")
    selected: list[Song] = []
    attempts = 0
    while len(selected) < DEFAULT_LETTER_NUM and attempts < 200:
        attempts += 1
        song = _weighted_song(ctx, key, _LETTER_WEIGHTS, pool, decay=0.5)
        if song is not None and song.id not in {item.id for item in selected}:
            selected.append(song)
    if len(selected) < DEFAULT_LETTER_NUM:
        return CommandResult.text("抽取开字母曲目失败，请稍后再试。")
    state = LetterGame(
        song_ids=[song.id for song in selected],
        song_titles=[song.title for song in selected],
        hidden_titles=[_encrypt_song_title(song.title) for song in selected],
        winners=["" for _ in selected],
        selected_range=label,
    )
    _ACTIVE_GAMES[key] = state
    return CommandResult.text(
        "开字母猜歌开启成功！使用 phi ltr n1 <曲名> 回答指定编号，phi open A 翻开字符，phi tip 随机提示，phi ans 公布答案。\n\n"
        + _letter_puzzle_text(state)
    )


async def _guess_song_answer(ctx: CommandContext, user_id: str, query: str, state: GuessIllGame | TipGame) -> CommandResult:
    song = _state_song(ctx, state)
    if song is None:
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("游戏数据已失效，已结束当前游戏。")
    if _is_correct_answer(ctx, query, song):
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return await _finish_with_answer(ctx, "恭喜，答对了！", song, state)
    best = ctx.searcher.best(query)
    wrong = best.title if best is not None else query
    return CommandResult.text(f"不是 {wrong} 哦，再想想吧。")


async def _guess_ill_tip(ctx: CommandContext, user_id: str, state: GuessIllGame) -> CommandResult:
    song = ctx.catalog.get(state.song_id)
    if song is None:
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("游戏数据已失效，已结束当前游戏。")
    action = _select_tip_action(state)
    tip = _apply_guess_tip(state, song, action)
    message = tip + _known_info_text(state.known_info)
    return await _image_game_result(ctx, message, state.image, "guess-tip")


async def _tip_game_next(ctx: CommandContext, user_id: str, state: TipGame) -> CommandResult:
    song = ctx.catalog.get(state.song_id)
    if song is None:
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("游戏数据已失效，已结束当前游戏。")
    if state.tip_count < len(state.tips):
        state.tip_count += 1
        return CommandResult.text(_tip_list(state.tips, state.tip_count))
    state.tip_count = len(state.tips) + 1
    message = "接下来是曲绘提示。请使用 phi guess <曲名> 回答。"
    return await _image_game_result(ctx, message, state.image, "tipgame")


def _guess_letter_answer(ctx: CommandContext, user_id: str, state: LetterGame, args: str) -> CommandResult:
    match = re.match(r"^(?:n|no\.?|第)?\s*([0-9一二三四五六七八九十]+)\s*[.。个首、]?\s*(.+)$", args, flags=re.I)
    if not match:
        return CommandResult.text("开字母回答格式：phi ltr n1 <曲名>，例如 phi ltr n1 Glaciaxion")
    index = _parse_number(match.group(1)) - 1
    query = match.group(2).strip()
    if index < 0 or index >= len(state.song_ids):
        return CommandResult.text(f"没有第 {index + 1} 首，请看清编号再回答。")
    if state.hidden_titles[index] is None:
        return CommandResult.text(f"第 {index + 1} 首已经被猜出啦。")
    song = ctx.catalog.get(state.song_ids[index])
    if song is None:
        return CommandResult.text("该编号的曲目信息已失效。")
    if not _is_correct_answer(ctx, query, song):
        best = ctx.searcher.best(query)
        wrong = best.title if best is not None else query
        return CommandResult.text(f"第 {index + 1} 首不是 {wrong}，再想想吧。")
    state.hidden_titles[index] = None
    state.winners[index] = user_id
    if _letter_all_guessed(state):
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("所有曲目均已被猜出，答案如下：\n" + _letter_answer_text(state))
    return CommandResult.text(f"恭喜，答对了！第 {index + 1} 首是 {song.title}。\n\n" + _letter_puzzle_text(state))


def _letter_open(ctx: CommandContext, user_id: str, state: LetterGame, letter: str) -> CommandResult:
    normalized = letter.casefold()
    display = letter.upper() if letter.isascii() and letter.isalpha() else letter
    if display in state.opened:
        return CommandResult.text(f"字符 {display} 已经翻开过了。")
    included = False
    for index, song_title in enumerate(state.song_titles):
        hidden = state.hidden_titles[index]
        if hidden is None:
            continue
        chars = list(song_title)
        hidden_chars = list(hidden)
        for pos, char in enumerate(chars):
            if _char_matches(char, normalized):
                hidden_chars[pos] = char
                included = True
        updated = "".join(hidden_chars)
        state.hidden_titles[index] = None if "*" not in updated else updated
    state.opened.append(display)
    if _letter_all_guessed(state):
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("所有字符均已翻开，答案如下：\n" + _letter_answer_text(state))
    prefix = f"成功翻开字符 {display}。" if included else f"这几首曲目中不包含字符 {display}。"
    return CommandResult.text(prefix + "\n\n" + _letter_puzzle_text(state))


def _letter_tip(ctx: CommandContext, user_id: str, state: LetterGame) -> CommandResult:
    candidates: list[str] = []
    for title, hidden in zip(state.song_titles, state.hidden_titles, strict=False):
        if hidden is None:
            continue
        for char, mask in zip(title, hidden, strict=False):
            if mask == "*":
                candidates.append(char)
    if not candidates:
        _ACTIVE_GAMES.pop(_session_key(ctx, user_id), None)
        return CommandResult.text("所有字符均已翻开，答案如下：\n" + _letter_answer_text(state))
    return _letter_open(ctx, user_id, state, random.choice(candidates))


async def _finish_with_answer(ctx: CommandContext, message: str, song: Song, state: GuessIllGame | TipGame) -> CommandResult:
    reveal = state.image
    reveal.style = 1
    reveal.ans = reveal.illustration
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        if ctx.sender is not None:
            await ctx.sender(CommandResult.text(f"{message}\n正确答案是：{song.title}"))
            reveal_path = await _render_guess_image(ctx, reveal, "guess-answer")
            await ctx.sender(CommandResult.image(reveal_path))
            song_path = await render_jinja_template(ctx, "atlas/atlas", jinja_adapter.atlas_data(ctx.paths, song), "guess-song")
            return CommandResult.image(song_path)
        reveal_path = await _render_guess_image(ctx, reveal, "guess-answer")
        return CommandResult.image(reveal_path)
    return CommandResult.text(f"{message}\n正确答案是：{song.title}\n\n{render.render_song(song)}")


async def _image_game_result(ctx: CommandContext, message: str, image: GuessImageData, name: str) -> CommandResult:
    if ctx.config.render_mode == "image" and ctx.html_render is not None:
        path = await _render_guess_image(ctx, image, name)
        if ctx.sender is not None:
            await ctx.sender(CommandResult.text(message))
        return CommandResult.image(path)
    return CommandResult.text(message)


async def _render_guess_image(ctx: CommandContext, image: GuessImageData, name: str):
    data = jinja_adapter.guess_data(ctx.paths, image.to_template())
    width = 2048 if image.style else image.width
    height = 1080 if image.style else image.height
    return await render_jinja_template(ctx, "guess/guess", data, name, width=width, height=height)


def _new_guess_image(ctx: CommandContext, song: Song, *, crop_min: int, crop_max: int) -> GuessImageData:
    path = ctx.find_illustration(song)
    if path is None:
        raise RuntimeError(f"missing illustration for {song.id}")
    width = random.randint(crop_min, crop_max)
    height = random.randint(crop_min, crop_max)
    return GuessImageData(
        illustration=original.image_data_uri(ctx.paths, path),
        width=width,
        height=height,
        x=random.randint(0, IMAGE_WIDTH - width),
        y=random.randint(0, IMAGE_HEIGHT - height),
    )


def _apply_initial_interference(image: GuessImageData, level: int) -> None:
    color_types = ["saturate", "invert", "hueRotate"]
    common_types = ["blur", "saturate", "invert", "hueRotate"]
    if level == 1:
        chosen = [random.choice(common_types)]
    elif level == 2:
        chosen = ["blur", random.choice(color_types)] if random.random() < 0.6 else ["lineMode"]
    else:
        chosen = ["blur", *random.sample(color_types, 2)] if random.random() < 0.7 else ["blur", "lineMode"]
    names = {"blur": "模糊", "saturate": "饱和", "invert": "反相", "hueRotate": "色相", "lineMode": "线稿"}
    for kind in chosen:
        if kind == "blur":
            image.blur = random.randint(8, 16)
        elif kind == "saturate":
            image.saturate = round(random.uniform(0.0, 0.3), 2) if random.random() < 0.5 else round(random.uniform(2.5, 4.0), 2)
        elif kind == "invert":
            image.invert = True
        elif kind == "hueRotate":
            image.hue_rotate = random.randint(60, 300)
        elif kind == "lineMode":
            image.line_mode = True
        image.chosen_interferences.append(names.get(kind, kind))


def _select_tip_action(state: GuessIllGame) -> int:
    if not state.actions:
        return 3
    weighted: list[tuple[int, int]] = []
    area = state.image.width * state.image.height
    for action in state.actions:
        if action == 0:
            weighted.append((action, max(1, int((1 - area / (IMAGE_WIDTH * IMAGE_HEIGHT)) * 100))))
        elif action == 1:
            weighted.append((action, max(1, int(state.image.blur / 16 * 30))))
        elif action == 2:
            weighted.append((action, max(1, int(len(state.remaining_info) / 6 * 50))))
        elif action == 3:
            weighted.append((action, random.randint(10, 50)))
        elif action == 4:
            weighted.append((action, max(1, _interference_weight(state.image))))
    return _weighted_choice(weighted)


def _apply_guess_tip(state: GuessIllGame, song: Song, action: int) -> str:
    image = state.image
    if action == 0:
        _area_increase(image, state.actions)
        return "[区域扩增]"
    if action == 1:
        image.blur = max(0, image.blur - 2)
        if image.blur <= 0 and 1 in state.actions:
            state.actions.remove(1)
        return "[清晰度上升]"
    if action == 2:
        _give_song_tip(state, song)
        return "[追加提示]"
    if action == 3:
        image.style = 1
        if 3 in state.actions:
            state.actions.remove(3)
        return "[全局视野]"
    if action == 4:
        reduced = _interference_reduce(image, state.actions)
        return f"[{reduced}干扰减弱]"
    return "[提示]"


def _area_increase(image: GuessImageData, actions: list[int]) -> None:
    size = 100
    if image.height < IMAGE_HEIGHT:
        if image.height + size >= IMAGE_HEIGHT:
            image.height = IMAGE_HEIGHT
            image.y = 0
        else:
            image.height += size
            image.y = max(0, min(image.y - size // 2, IMAGE_HEIGHT - image.height))
    if image.width < IMAGE_WIDTH:
        if image.width + size >= IMAGE_WIDTH:
            image.width = IMAGE_WIDTH
            image.x = 0
            if 0 in actions:
                actions.remove(0)
        else:
            image.width += size
            image.x = max(0, min(image.x - size // 2, IMAGE_WIDTH - image.width))


def _give_song_tip(state: GuessIllGame, song: Song) -> None:
    if not state.remaining_info:
        if 2 in state.actions:
            state.actions.remove(2)
        return
    key = random.choice(state.remaining_info)
    state.remaining_info.remove(key)
    if not state.remaining_info and 2 in state.actions:
        state.actions.remove(2)
    if key == "chart":
        charts = song.display_charts()
        if not charts:
            return
        chart = random.choice(charts)
        variants = [
            f"该曲目的 {chart.rank} 谱面定数为 {chart.difficulty_text or chart.difficulty or '?'}",
            f"该曲目的 {chart.rank} 谱面物量为 {chart.combo or '未知'}",
            f"该曲目的 {chart.rank} 谱面谱师为 {chart.charter or '未知'}",
        ]
        state.known_info[key] = random.choice(variants)
        return
    labels = {
        "chapter": "该曲目隶属于",
        "bpm": "该曲目的 BPM 值为",
        "composer": "该曲目的作者为",
        "length": "该曲目的时长为",
        "illustrator": "该曲目曲绘的作者为",
    }
    value = getattr(song, key, "") or "未知"
    state.known_info[key] = f"{labels.get(key, key)} {value}"


def _interference_reduce(image: GuessImageData, actions: list[int]) -> str:
    candidates: list[str] = []
    if image.saturate != 1:
        candidates.append("saturate")
    if image.invert:
        candidates.append("invert")
    if image.hue_rotate:
        candidates.append("hueRotate")
    if image.line_mode:
        candidates.append("lineMode")
    if not candidates:
        if 4 in actions:
            actions.remove(4)
        return "额外"
    target = random.choice(candidates)
    names = {"saturate": "饱和度", "invert": "反相", "hueRotate": "色相", "lineMode": "线稿"}
    if target == "saturate":
        step = round(random.uniform(0.2, 0.5), 2)
        image.saturate = min(1, image.saturate + step) if image.saturate < 1 else max(1, image.saturate - step)
    elif target == "invert":
        image.invert = False
    elif target == "hueRotate":
        step = random.randint(20, 40)
        image.hue_rotate = 0 if abs(image.hue_rotate) <= step else max(0, image.hue_rotate - step)
    elif target == "lineMode":
        image.line_mode = False
    if not _has_non_blur_interference(image) and 4 in actions:
        actions.remove(4)
    return names.get(target, target)


def _has_non_blur_interference(image: GuessImageData) -> bool:
    return image.line_mode or image.saturate != 1 or image.invert or bool(image.hue_rotate)


def _interference_weight(image: GuessImageData) -> int:
    return sum(
        [
            15 if image.saturate != 1 else 0,
            5 if image.invert else 0,
            20 if image.hue_rotate else 0,
            5 if image.line_mode else 0,
        ]
    )


def _known_info_text(known: dict[str, str]) -> str:
    lines = [value for value in known.values() if value]
    return ("\n" + "\n".join(lines)) if lines else ""


def _song_tips(song: Song) -> list[str]:
    tips = [
        f"这首曲目隶属于 {song.chapter or '未知章节'}",
        f"这首曲目的 BPM 值为 {song.bpm or '未知'}",
        f"这首曲目的作曲者为 {song.composer or '未知'}",
        f"这首曲目的时长为 {song.length or '未知'}",
        f"这首曲目的画师为 {song.illustrator or '未知'}",
    ]
    for chart in song.display_charts():
        tips.append(f"这首曲目的 {chart.rank} 难度定数为 {chart.difficulty_text or chart.difficulty or '未知'}")
        tips.append(f"这首曲目的 {chart.rank} 难度物量为 {chart.combo or '未知'}")
        tips.append(f"这首曲目的 {chart.rank} 谱师为 {chart.charter or '未知'}")
    return tips


def _tip_list(tips: list[str], count: int) -> str:
    shown = tips[: max(1, min(count, len(tips)))]
    return "\n".join(f"{index}. {tip}" for index, tip in enumerate(shown, 1))


def _letter_pool(ctx: CommandContext, args: str) -> tuple[list[Song], str]:
    tokens = [token.casefold() for token in re.split(r"\s+", args.strip()) if token.strip()]
    all_songs = ctx.catalog.all_songs()
    if not tokens or tokens == ["pgr"]:
        return all_songs, "pgr"
    pool = [
        song
        for song in all_songs
        if any(token in song.chapter.casefold() or token in song.title.casefold() for token in tokens)
    ]
    return (pool, "、".join(tokens)) if pool else (all_songs, "pgr")


def _letter_puzzle_text(state: LetterGame) -> str:
    lines = [f"曲库范围：{state.selected_range}", "当前所有翻开的字符：" + (" ".join(state.opened) if state.opened else "无")]
    for index, (title, hidden, winner) in enumerate(zip(state.song_titles, state.hidden_titles, state.winners, strict=False), 1):
        if hidden is None:
            suffix = f" @{winner}" if winner else ""
            lines.append(f"{index}. {title} √{suffix}")
        else:
            lines.append(f"{index}. {hidden}")
    return "\n".join(lines)


def _letter_answer_text(state: LetterGame) -> str:
    lines = []
    for index, (title, winner) in enumerate(zip(state.song_titles, state.winners, strict=False), 1):
        suffix = f" @{winner}" if winner else ""
        lines.append(f"{index}. {title}{suffix}")
    return "\n".join(lines)


def _encrypt_song_title(title: str) -> str:
    return "".join(" " if char.isspace() or char == "\u00a0" else "*" for char in title)


def _letter_all_guessed(state: LetterGame) -> bool:
    return all(hidden is None for hidden in state.hidden_titles)


def _char_matches(char: str, normalized: str) -> bool:
    if char.casefold() == normalized:
        return True
    if lazy_pinyin is None or Style is None:
        return False
    try:
        initials = lazy_pinyin(char, style=Style.FIRST_LETTER, errors="ignore")
    except Exception:
        return False
    return any(item.casefold() == normalized for item in initials)


def _is_correct_answer(ctx: CommandContext, query: str, song: Song) -> bool:
    hits = ctx.searcher.search(query, limit=8)
    return any(hit.song.id == song.id and hit.score >= 0.95 for hit in hits)


def _state_song(ctx: CommandContext, state: GuessIllGame | TipGame | LetterGame) -> Song | None:
    if isinstance(state, LetterGame):
        return ctx.catalog.get(state.song_ids[0]) if state.song_ids else None
    return ctx.catalog.get(state.song_id)


def _songs_with_illustrations(ctx: CommandContext) -> list[Song]:
    return [song for song in ctx.catalog.all_songs() if ctx.find_illustration(song) is not None]


def _weighted_song(
    ctx: CommandContext,
    key: str,
    weight_store: dict[str, dict[str, float]],
    pool: list[Song],
    *,
    decay: float,
) -> Song | None:
    if not pool:
        return None
    weights = weight_store.setdefault(key, {})
    for song in pool:
        weights.setdefault(song.id, 1.0)
    total = sum(max(0.001, weights.get(song.id, 1.0)) for song in pool)
    needle = random.uniform(0, total)
    current = 0.0
    for song in pool:
        current += max(0.001, weights.get(song.id, 1.0))
        if current >= needle:
            weights[song.id] = max(0.001, weights.get(song.id, 1.0) * decay)
            return song
    return random.choice(pool)


def _weighted_choice(weighted: list[tuple[int, int]]) -> int:
    total = sum(max(1, weight) for _, weight in weighted)
    needle = random.randint(1, total)
    current = 0
    for value, weight in weighted:
        current += max(1, weight)
        if current >= needle:
            return value
    return weighted[-1][0]


def _parse_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if value.endswith("十"):
        return digits.get(value[:-1], 0) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 1) * 10 + digits.get(right, 0)
    return digits.get(value, 0)


def _current_game(ctx: CommandContext, user_id: str) -> GameState | None:
    return _ACTIVE_GAMES.get(_session_key(ctx, user_id))


def _session_key(ctx: CommandContext, user_id: str) -> str:
    return ctx.session_id or user_id
