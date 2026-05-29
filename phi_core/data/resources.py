from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
import random
import re
from typing import Any

import yaml


@dataclass(slots=True)
class VersionLog:
    version_label: str
    version_code: int
    whatsnew: str
    changes: list[dict[str, str]]


def load_tips(info_dir: Path) -> list[str]:
    path = Path(info_dir) / "tips.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item is not None and str(item).strip()]


def random_tip(info_dir: Path, rng: random.Random | None = None) -> str | None:
    tips = load_tips(info_dir)
    if not tips:
        return None
    return (rng or random.Random()).choice(tips)


def load_notice(info_dir: Path) -> dict[str, Any]:
    path = Path(info_dir) / "notice.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def latest_version_log(info_dir: Path) -> VersionLog | None:
    old_info = Path(info_dir) / "oldInfo"
    versions = []
    if old_info.exists():
        for folder in old_info.iterdir():
            if folder.is_dir() and folder.name.isdigit():
                versions.append(int(folder.name))
    if not versions:
        return None
    return load_version_log(info_dir, max(versions))


def load_version_log(info_dir: Path, version: int | str) -> VersionLog | None:
    folder = Path(info_dir) / "oldInfo" / str(version)
    info_path = folder / "info.json"
    if not info_path.exists():
        return None
    info = json.loads(info_path.read_text(encoding="utf-8-sig"))
    if not isinstance(info, dict):
        return None
    changes: list[dict[str, str]] = []
    change_path = folder / "change.csv"
    if change_path.exists():
        with change_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("id"):
                    changes.append({str(key): str(value or "") for key, value in row.items()})
    return VersionLog(
        version_label=str(info.get("version_label") or info.get("version") or version),
        version_code=_as_int(info.get("version_code"), int(version) if str(version).isdigit() else 0),
        whatsnew=_strip_html(str(info.get("whatsnew") or "")),
        changes=changes,
    )


def resolve_version_code(info_dir: Path, raw: str) -> int | None:
    text = raw.strip()
    if not text:
        latest = latest_version_log(info_dir)
        return latest.version_code if latest else None
    old_info = Path(info_dir) / "oldInfo"
    if text.isdigit():
        code = int(text)
        return code if (old_info / str(code) / "info.json").exists() else None
    for folder in old_info.iterdir() if old_info.exists() else []:
        info_path = folder / "info.json"
        if not info_path.exists():
            continue
        try:
            info = json.loads(info_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if str(info.get("version_label") or "").casefold() == text.casefold():
            return _as_int(info.get("version_code"), int(folder.name) if folder.name.isdigit() else 0)
    return None


def _strip_html(value: str) -> str:
    text = value.replace("<br/>", "\n").replace("<br>", "\n").replace("<br />", "\n")
    return re.sub(r"<[^>]+>", "", text).strip()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
