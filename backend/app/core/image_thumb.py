"""On-demand image thumbnails with storage-backed cache.

List/detail UIs only need small previews; serving multi-MB originals is the main
cause of slow image-heavy pages. Thumbnails are generated with Pillow, cached
under ``_thumbs/`` next to (or in the same storage as) originals, and re-used.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path

from app.core.storage import Storage

logger = logging.getLogger(__name__)

# List/grid previews: ~2× retina for ~200–320px tiles
DEFAULT_THUMB_EDGE = 640
DEFAULT_THUMB_QUALITY = 78

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def infer_media_type(relative_path: str, fallback: str = "application/octet-stream") -> str:
    suffix = Path(relative_path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(suffix, fallback)


def thumb_cache_rel(source_path: str, max_edge: int) -> str:
    """Stable cache key under ``_thumbs/`` for a source object + size."""
    rel = source_path.replace("\\", "/").lstrip("/")
    stem = _SAFE_RE.sub("_", rel.replace("/", "__"))
    # Keep path reasonably short for local FS / OSS keys
    if len(stem) > 180:
        stem = f"{stem[:80]}_{abs(hash(rel)) & 0xFFFFFFFF:08x}_{stem[-60:]}"
    return f"_thumbs/{stem}_w{int(max_edge)}.jpg"


def make_thumb_bytes(
    data: bytes,
    *,
    max_edge: int = DEFAULT_THUMB_EDGE,
    quality: int = DEFAULT_THUMB_QUALITY,
) -> bytes | None:
    """Resize image to fit within max_edge and return JPEG bytes. None on failure."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("Pillow not available; cannot generate thumbnails")
        return None

    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception:
        logger.debug("thumbnail: cannot open image", exc_info=True)
        return None

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Animated GIF / multi-frame: first frame only
    try:
        if getattr(img, "n_frames", 1) > 1:
            img.seek(0)
    except Exception:
        pass

    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode == "P":
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        if "A" in img.getbands():
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def read_image_variant(
    storage: Storage,
    source_path: str,
    *,
    thumb: bool = False,
    max_edge: int = DEFAULT_THUMB_EDGE,
    original_media_type: str | None = None,
) -> tuple[bytes, str]:
    """
    Read original or a cached JPEG thumbnail.

    Returns ``(bytes, media_type)``. On thumb failure, falls back to original.
    """
    data = storage.read(source_path)
    media = original_media_type or infer_media_type(source_path)
    if not media.startswith("image/"):
        media = infer_media_type(source_path, media)

    if not thumb:
        return data, media

    edge = max(64, min(int(max_edge or DEFAULT_THUMB_EDGE), 1280))
    cache_rel = thumb_cache_rel(source_path, edge)
    try:
        if storage.exists(cache_rel):
            return storage.read(cache_rel), "image/jpeg"
    except Exception:
        logger.debug("thumbnail cache read/exists failed for %s", cache_rel, exc_info=True)

    thumb_data = make_thumb_bytes(data, max_edge=edge)
    if not thumb_data:
        return data, media

    # Prefer the smaller payload (JPEG re-encode may lose to already-tiny originals)
    if len(thumb_data) >= len(data):
        return data, media

    try:
        storage.save(cache_rel, thumb_data)
    except Exception:
        logger.warning("failed to cache thumbnail %s", cache_rel, exc_info=True)

    return thumb_data, "image/jpeg"
