from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

TOKEN_RE = re.compile(r"^[A-Za-z0-9]{25}$")
API_ID_RE = re.compile(r"^[0-9]+$")


class StoreError(RuntimeError):
    pass


class SaveStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.saves_dir = self.data_dir / "saves"
        self.histories_dir = self.data_dir / "history"
        self.bindings_path = self.data_dir / "bindings.json"
        self.api_ids_path = self.data_dir / "api_ids.json"
        self.custom_aliases_path = self.data_dir / "custom_aliases.yaml"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.saves_dir.mkdir(parents=True, exist_ok=True)
        self.histories_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_token(token: str) -> bool:
        return bool(TOKEN_RE.match(token.strip()))

    @staticmethod
    def validate_api_id(api_id: str) -> bool:
        return bool(API_ID_RE.match(api_id.strip()))

    def get_token(self, user_id: str) -> str | None:
        return self._load_bindings().get(str(user_id))

    def get_api_id(self, user_id: str) -> str | None:
        return self._load_api_ids().get(str(user_id))

    def bind(self, user_id: str, token: str, api_id: str | None = None) -> None:
        token = token.strip()
        if not self.validate_token(token):
            raise StoreError("sessionToken 格式应为 25 位英数字。")
        bindings = self._load_bindings()
        bindings[str(user_id)] = token
        self._save_bindings(bindings)
        if api_id:
            self.set_api_id(user_id, api_id)

    def set_api_id(self, user_id: str, api_id: str) -> None:
        api_id = api_id.strip()
        if not self.validate_api_id(api_id):
            raise StoreError("查询 ID 应为纯数字。")
        api_ids = self._load_api_ids()
        api_ids[str(user_id)] = api_id
        self._save_api_ids(api_ids)

    def clear_token(self, user_id: str) -> bool:
        user_id = str(user_id)
        bindings = self._load_bindings()
        existed = user_id in bindings
        bindings.pop(user_id, None)
        self._save_bindings(bindings)
        return existed

    def clear_api_id(self, user_id: str) -> bool:
        user_id = str(user_id)
        api_ids = self._load_api_ids()
        existed = user_id in api_ids
        api_ids.pop(user_id, None)
        self._save_api_ids(api_ids)
        return existed

    def clear_snapshot(self, user_id: str) -> bool:
        path = self.save_path(user_id)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    def clear_history(self, user_id: str) -> bool:
        path = self.history_path(user_id)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed

    def unbind(self, user_id: str) -> bool:
        user_id = str(user_id)
        bindings = self._load_bindings()
        api_ids = self._load_api_ids()
        existed = (
            user_id in bindings
            or user_id in api_ids
            or self.save_path(user_id).exists()
            or self.history_path(user_id).exists()
        )
        bindings.pop(user_id, None)
        api_ids.pop(user_id, None)
        self._save_bindings(bindings)
        self._save_api_ids(api_ids)
        self.save_path(user_id).unlink(missing_ok=True)
        self.history_path(user_id).unlink(missing_ok=True)
        return existed

    def clean(self, user_id: str) -> bool:
        return self.unbind(user_id)

    def save_snapshot(self, user_id: str, snapshot: dict[str, Any]) -> None:
        path = self.save_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_snapshot(self, user_id: str) -> dict[str, Any] | None:
        path = self.save_path(user_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_history(self, user_id: str, history: dict[str, Any]) -> None:
        path = self.history_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_history(self, user_id: str) -> dict[str, Any]:
        path = self.history_path(user_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def load_custom_aliases(self) -> dict[str, list[str]]:
        if not self.custom_aliases_path.exists():
            return {}
        try:
            data = yaml.safe_load(self.custom_aliases_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}
        if not isinstance(data, dict):
            return {}
        result: dict[str, list[str]] = {}
        for key, value in data.items():
            aliases: list[str] = []
            if isinstance(value, list):
                aliases = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                aliases = [value.strip()]
            if aliases:
                result[str(key)] = aliases
        return result

    def add_custom_alias(self, song_id: str, alias: str) -> bool:
        song_id = song_id.strip()
        alias = alias.strip()
        if not song_id or not alias:
            raise StoreError("曲目 ID 和别名不能为空。")
        aliases = self.load_custom_aliases()
        values = aliases.setdefault(song_id, [])
        if alias in values:
            return False
        values.append(alias)
        self.custom_aliases_path.parent.mkdir(parents=True, exist_ok=True)
        self.custom_aliases_path.write_text(
            yaml.safe_dump(aliases, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
        return True

    def save_path(self, user_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(user_id))
        return self.saves_dir / f"{safe}.json"

    def history_path(self, user_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(user_id))
        return self.histories_dir / f"{safe}.json"

    def _load_bindings(self) -> dict[str, str]:
        if not self.bindings_path.exists():
            return {}
        try:
            data = json.loads(self.bindings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def _save_bindings(self, bindings: dict[str, str]) -> None:
        self.bindings_path.write_text(json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_api_ids(self) -> dict[str, str]:
        if not self.api_ids_path.exists():
            return {}
        try:
            data = json.loads(self.api_ids_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def _save_api_ids(self, api_ids: dict[str, str]) -> None:
        self.api_ids_path.write_text(json.dumps(api_ids, ensure_ascii=False, indent=2), encoding="utf-8")
