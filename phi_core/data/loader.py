from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from ..models import LEVELS, Song, SongChart


@dataclass(slots=True)
class SongCatalog:
    songs: dict[str, Song]
    alias_to_id: dict[str, str]

    def __len__(self) -> int:
        return len(self.songs)

    def all_songs(self) -> list[Song]:
        return list(self.songs.values())

    def get(self, song_id: str) -> Song | None:
        normalized = normalize_song_id(song_id)
        return self.songs.get(normalized)


class CatalogLoadError(RuntimeError):
    pass


def normalize_key(value: str) -> str:
    return "".join(str(value).casefold().split())


def normalize_song_id(value: str) -> str:
    value = str(value).strip()
    return value[:-2] if value.endswith(".0") else value


def load_catalog(info_dir: Path) -> SongCatalog:
    info_dir = Path(info_dir)
    info_csv = info_dir / "info.csv"
    difficulty_csv = info_dir / "difficulty.csv"
    infolist_json = info_dir / "infolist.json"
    nicklist_yaml = info_dir / "nicklist.yaml"
    spinfo_json = info_dir / "spinfo.json"
    otherinfo_yaml = info_dir / "otherinfo.yaml"
    notes_info_json = info_dir / "notesInfo.json"

    if not info_csv.exists() or not difficulty_csv.exists():
        raise CatalogLoadError(f"missing required phi info resources in {info_dir}")

    difficulties = _read_difficulty_csv(difficulty_csv)
    extra_info = _read_json(infolist_json, {})
    sp_info = _read_json(spinfo_json, {})
    other_info = _read_yaml(otherinfo_yaml, {})
    aliases_raw = _read_yaml(nicklist_yaml, {})
    notes_info = _read_json(notes_info_json, {})

    songs: dict[str, Song] = {}
    with info_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            raw_id = (row.get("id") or "").strip()
            if not raw_id:
                continue
            song_id = normalize_song_id(raw_id)
            meta = extra_info.get(song_id, {}) if isinstance(extra_info, dict) else {}
            diff_row = difficulties.get(song_id, {})
            charts: dict[str, SongChart] = {}
            for rank in LEVELS:
                chart_author = (row.get(rank) or "").strip()
                difficulty = _parse_float(diff_row.get(rank, ""))
                if chart_author or difficulty is not None:
                    charts[rank] = SongChart(
                        rank=rank,
                        difficulty=difficulty,
                        difficulty_text="" if difficulty is None else f"{difficulty:.1f}",
                        charter=chart_author,
                    )
            song = Song(
                id=song_id,
                title=(row.get("song") or song_id).strip(),
                composer=(row.get("composer") or "").strip(),
                illustrator=(row.get("illustrator") or "").strip(),
                bpm=str(meta.get("bpm", "") or ""),
                length=str(meta.get("length", "") or ""),
                chapter=str(meta.get("chapter", "") or ""),
                is_original=meta.get("isOriginal") if isinstance(meta, dict) else None,
                charts=charts,
            )
            songs[song_id] = song

    _merge_sp_songs(songs, sp_info)
    _merge_other_songs(songs, other_info)
    _merge_note_counts(songs, notes_info)

    alias_to_id: dict[str, str] = {}
    for song in songs.values():
        for value in {song.id, song.id_with_suffix, song.title}:
            key = normalize_key(value)
            if key:
                alias_to_id.setdefault(key, song.id)

    if isinstance(aliases_raw, dict):
        for target, aliases in aliases_raw.items():
            song_id = _resolve_alias_target(str(target), songs)
            if not song_id:
                continue
            song = songs[song_id]
            for alias in _coerce_aliases(aliases):
                if alias and alias not in song.aliases:
                    song.aliases.append(alias)
                key = normalize_key(alias)
                if key:
                    alias_to_id.setdefault(key, song_id)

    return SongCatalog(songs=songs, alias_to_id=alias_to_id)


def apply_aliases(catalog: SongCatalog, aliases_raw: Any) -> None:
    """Merge user-managed aliases into an already loaded catalog."""
    if not isinstance(aliases_raw, dict):
        return
    for target, aliases in aliases_raw.items():
        song_id = _resolve_alias_target(str(target), catalog.songs)
        if not song_id:
            continue
        song = catalog.songs[song_id]
        for alias in _coerce_aliases(aliases):
            alias = alias.strip()
            if not alias:
                continue
            if alias not in song.aliases:
                song.aliases.append(alias)
            key = normalize_key(alias)
            if key:
                catalog.alias_to_id[key] = song_id


def _read_difficulty_csv(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            song_id = normalize_song_id(row.get("id", ""))
            if song_id:
                result[song_id] = row
    return result


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    # The upstream nicklist contains a few tab characters; PyYAML correctly
    # rejects them, but Yunzai's loader tolerated the file. Normalize on read.
    return yaml.safe_load(text.replace("\t", "  ")) or default


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _merge_sp_songs(songs: dict[str, Song], sp_info: Any) -> None:
    if not isinstance(sp_info, dict):
        return
    for raw_id, data in sp_info.items():
        if not isinstance(data, dict):
            continue
        song_id = normalize_song_id(str(raw_id))
        charts: dict[str, SongChart] = {}
        raw_charts = data.get("chart", {})
        if isinstance(raw_charts, dict):
            for rank, chart in raw_charts.items():
                if not isinstance(chart, dict):
                    continue
                difficulty = _parse_float(chart.get("difficulty"))
                charts[str(rank)] = SongChart(
                    rank=str(rank),
                    difficulty=difficulty,
                    difficulty_text=str(chart.get("difficulty", "") or ""),
                    level=str(chart.get("level", "") or ""),
                    combo=_parse_int(chart.get("combo")),
                    charter=str(chart.get("charter", "") or ""),
                    rgba=str(chart.get("rgba", "") or ""),
                )
        songs.setdefault(
            song_id,
            Song(
                id=song_id,
                title=str(data.get("song", song_id) or song_id),
                composer=str(data.get("composer", "") or ""),
                illustrator=str(data.get("illustrator", "") or ""),
                bpm=str(data.get("bpm", "") or ""),
                length=str(data.get("length", "") or ""),
                chapter=str(data.get("chapter", "SP") or "SP"),
                illustration=str(data.get("illustration", "") or ""),
                illustration_big=str(data.get("illustration_big", "") or ""),
                sp_info=str(data.get("spinfo", "") or ""),
                is_original=data.get("isOriginal"),
                charts=charts,
            ),
        )


def _merge_other_songs(songs: dict[str, Song], other_info: Any) -> None:
    if not isinstance(other_info, dict):
        return
    for raw_key, data in other_info.items():
        if not isinstance(data, dict):
            continue
        song_id = normalize_song_id(str(data.get("id") or raw_key))
        charts: dict[str, SongChart] = {}
        raw_charts = data.get("chart", {})
        if isinstance(raw_charts, dict):
            for rank, chart in raw_charts.items():
                if not isinstance(chart, dict):
                    continue
                difficulty = _parse_float(chart.get("difficulty"))
                charts[str(rank)] = SongChart(
                    rank=str(rank),
                    difficulty=difficulty,
                    difficulty_text=str(chart.get("difficulty", "") or ""),
                    level=str(chart.get("level", "") or ""),
                    combo=_parse_int(chart.get("combo")),
                    charter=str(chart.get("charter", "") or ""),
                    rgba=str(chart.get("rgba", "") or ""),
                )
        songs[song_id] = Song(
            id=song_id,
            title=str(data.get("song", song_id) or song_id),
            composer=str(data.get("composer", "") or ""),
            illustrator=str(data.get("illustrator", "") or ""),
            bpm=str(data.get("bpm", "") or ""),
            length=str(data.get("length", "") or ""),
            chapter=str(data.get("chapter", "") or ""),
            illustration=str(data.get("illustration", "") or ""),
            illustration_big=str(data.get("illustration_big", "") or ""),
            sp_info=str(data.get("spinfo", "") or ""),
            is_original=data.get("isOriginal"),
            charts=charts,
        )


def _merge_note_counts(songs: dict[str, Song], notes_info: Any) -> None:
    if not isinstance(notes_info, dict):
        return
    for raw_id, ranks in notes_info.items():
        song_id = normalize_song_id(str(raw_id))
        song = songs.get(song_id)
        if song is None or not isinstance(ranks, dict):
            continue
        for rank, data in ranks.items():
            chart = song.charts.get(str(rank))
            if chart is None or not isinstance(data, dict):
                continue
            totals = data.get("t")
            if isinstance(totals, list):
                combo = 0
                for value in totals:
                    parsed = _parse_int(value)
                    if parsed is not None:
                        combo += parsed
                if combo > 0:
                    chart.combo = combo


def _resolve_alias_target(target: str, songs: dict[str, Song]) -> str | None:
    normalized = normalize_song_id(target)
    if normalized in songs:
        return normalized
    target_key = normalize_key(target)
    for song in songs.values():
        if normalize_key(song.title) == target_key or normalize_key(song.id) == target_key:
            return song.id
    return None


def _coerce_aliases(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        for item in value:
            if item is not None:
                yield str(item)
    elif isinstance(value, str):
        yield value
