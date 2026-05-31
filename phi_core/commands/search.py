from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .common import CommandContext, CommandResult
from ..models import Song
from ..render import text as render

ALIASES = {"search", "查找", "检索"}


def handle(ctx: CommandContext, user_id: str, args: str) -> CommandResult:
    if not args:
        return CommandResult.text(render.render_need_query("search"))
    filter_result = _filter_search(ctx, args)
    if filter_result is not None:
        return CommandResult.text(filter_result)
    return CommandResult.text(render.render_search(args, ctx.searcher.search(args, limit=10)))


@dataclass(slots=True)
class _SearchRange:
    low: float
    high: float

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def label(self) -> str:
        if abs(self.low - self.high) < 0.0001:
            return _fmt_number(self.low)
        return f"{_fmt_number(self.low)}-{_fmt_number(self.high)}"


@dataclass(slots=True)
class _FilterSpec:
    name: str
    label: str
    pattern: re.Pattern[str]
    int_bucket: bool
    predicate: Callable[[Song, _SearchRange], bool]


_SEPARATOR = r"[\s:：,，/|~是为]*"
_FILTERS: tuple[_FilterSpec, ...] = (
    _FilterSpec(
        name="bpm",
        label="BPM",
        pattern=re.compile(rf"bpm{_SEPARATOR}([0-9]+(?:\s*-\s*[0-9]+)?)", re.IGNORECASE),
        int_bucket=False,
        predicate=lambda song, value_range: any(value_range.contains(value) for value in _bpm_values(song)),
    ),
    _FilterSpec(
        name="difficulty",
        label="定级",
        pattern=re.compile(rf"(?:difficulty|dif|定数|难度|定级){_SEPARATOR}([0-9.]+(?:\s*-\s*[0-9.]+)?)", re.IGNORECASE),
        int_bucket=True,
        predicate=lambda song, value_range: any(
            chart.difficulty is not None and value_range.contains(float(chart.difficulty))
            for chart in song.display_charts()
        ),
    ),
    _FilterSpec(
        name="combo",
        label="物量",
        pattern=re.compile(rf"(?:combo|cmb|物量|连击){_SEPARATOR}([0-9]+(?:\s*-\s*[0-9]+)?)", re.IGNORECASE),
        int_bucket=False,
        predicate=lambda song, value_range: any(
            chart.combo is not None and value_range.contains(float(chart.combo))
            for chart in song.display_charts()
        ),
    ),
)


def _filter_search(ctx: CommandContext, args: str) -> str | None:
    active: list[tuple[_FilterSpec, _SearchRange]] = []
    for spec in _FILTERS:
        match = spec.pattern.search(args)
        if not match:
            continue
        active.append((spec, _parse_filter_range(match.group(1), int_bucket=spec.int_bucket)))
    if not active:
        return None

    songs = ctx.catalog.all_songs()
    for spec, value_range in active:
        songs = [song for song in songs if spec.predicate(song, value_range)]
    songs = sorted(songs, key=lambda song: song.id.casefold())
    return _render_filter_results(songs, active)


def _parse_filter_range(raw: str, *, int_bucket: bool) -> _SearchRange:
    text = re.sub(r"\s+", "", raw)
    if "-" in text:
        left, right = text.split("-", 1)
    else:
        left = right = text
    low = _to_float(left)
    high = _to_float(right)
    if int_bucket and high.is_integer() and ".0" not in text:
        high += 0.9
    low, high = sorted((low, high))
    return _SearchRange(low=low, high=high)


def _render_filter_results(songs: list[Song], active: list[tuple[_FilterSpec, _SearchRange]]) -> str:
    lines = [f"找到了{len(songs)}首曲目喵！", "当前筛选："]
    lines.extend(f"{spec.label}:{value_range.label()}" for spec, value_range in active)
    shown = songs[:50]
    for song in shown:
        lines.append("")
        lines.append(f"{song.id}")
        lines.append(f"BPM:{song.bpm or '-'}")
        for chart in song.display_charts():
            difficulty = _fmt_number(float(chart.difficulty)) if chart.difficulty is not None else "-"
            combo = chart.combo if chart.combo is not None else "-"
            lines.append(f"{chart.rank} {difficulty} {combo}")
    if len(songs) > len(shown):
        lines.append("")
        lines.append(f"结果过多，当前仅显示前 {len(shown)} 首。")
    return "\n".join(lines)


def _bpm_values(song: Song) -> list[float]:
    return [_to_float(value) for value in re.findall(r"\d+(?:\.\d+)?", song.bpm)]


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")
