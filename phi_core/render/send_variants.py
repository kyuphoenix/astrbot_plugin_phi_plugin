from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

MAX_LOSSY_PIXELS = 16_000_000
MAX_LOSSY_SIDE = 4096


@dataclass(frozen=True)
class ImageSendVariant:
    name: str
    data: bytes


def build_image_send_variants(path: str | Path) -> list[ImageSendVariant]:
    return [build_image_send_variant(path, name) for name in ("original", "jpg", "webp")]


def build_image_send_variant(path: str | Path, name: str) -> ImageSendVariant:
    """Build one image byte variant for platform send fallback."""
    image_path = Path(path)
    if name == "original":
        return ImageSendVariant("original", image_path.read_bytes())

    with _open_image_for_fallback(image_path) as image:
        flattened = _resize_for_send(_flatten_for_lossy(image))
        if name == "jpg":
            return ImageSendVariant("jpg", _save_to_bytes(flattened, "JPEG", quality=86, optimize=True))
        if name == "webp":
            return ImageSendVariant("webp", _save_to_bytes(flattened, "WEBP", quality=82, method=6))

    raise ValueError(f"unsupported image send variant: {name}")


def _open_image_for_fallback(image_path: Path) -> Image.Image:
    previous_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        image = Image.open(image_path)
        image.load()
        return image
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit


def _resize_for_send(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    scale = min(
        1.0,
        MAX_LOSSY_SIDE / max(width, height),
        (MAX_LOSSY_PIXELS / (width * height)) ** 0.5,
    )
    if scale >= 1.0:
        return image
    resized = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)
    image.close()
    return resized


def _flatten_for_lossy(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _save_to_bytes(image: Image.Image, fmt: str, **params: object) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=fmt, **params)
    return buffer.getvalue()
