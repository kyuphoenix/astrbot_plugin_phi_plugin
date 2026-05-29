from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    if "Comp.Image.fromFileSystem" in source:
        raise SystemExit("main.py should not send image results via file paths")
    if "fromBytes" not in source or "fromBase64" not in source:
        raise SystemExit("main.py should send image results via bytes/base64")
    print("send component smoke passed")


if __name__ == "__main__":
    main()
