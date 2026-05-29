from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"^[A-Za-z0-9]{25}$")


class StoreError(RuntimeError):
    pass


class SaveStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.saves_dir = self.data_dir / "saves"
        self.bindings_path = self.data_dir / "bindings.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_token(token: str) -> bool:
        return bool(TOKEN_RE.match(token.strip()))

    def get_token(self, user_id: str) -> str | None:
        return self._load_bindings().get(str(user_id))

    def bind(self, user_id: str, token: str) -> None:
        token = token.strip()
        if not self.validate_token(token):
            raise StoreError("sessionToken 格式应为 25 位英数字。")
        bindings = self._load_bindings()
        bindings[str(user_id)] = token
        self._save_bindings(bindings)

    def unbind(self, user_id: str) -> bool:
        user_id = str(user_id)
        bindings = self._load_bindings()
        existed = user_id in bindings or self.save_path(user_id).exists()
        bindings.pop(user_id, None)
        self._save_bindings(bindings)
        self.save_path(user_id).unlink(missing_ok=True)
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

    def save_path(self, user_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(user_id))
        return self.saves_dir / f"{safe}.json"

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
