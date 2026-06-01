from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phi_core.render.send_variants import build_image_send_variants


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "source.png"
        image = Image.new("RGBA", (64, 48), (20, 90, 160, 180))
        image.save(image_path, format="PNG")

        variants = build_image_send_variants(image_path)

    names = [variant.name for variant in variants]
    if names != ["original", "jpg", "webp"]:
        raise SystemExit(f"unexpected variant order: {names}")

    original, jpg, webp = [variant.data for variant in variants]
    if not original.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit("original variant should preserve PNG bytes")
    if not jpg.startswith(b"\xff\xd8"):
        raise SystemExit("jpg variant is not a JPEG file")
    if not (webp.startswith(b"RIFF") and webp[8:12] == b"WEBP"):
        raise SystemExit("webp variant is not a WebP file")
    if min(len(original), len(jpg), len(webp)) <= 0:
        raise SystemExit("image variants should not be empty")

    print("image send variants smoke passed")


if __name__ == "__main__":
    main()
