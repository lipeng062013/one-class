"""Unit tests for on-demand image thumbnails."""

from io import BytesIO

from PIL import Image

from app.core.image_thumb import make_thumb_bytes, read_image_variant, thumb_cache_rel
from app.core.storage import LocalStorage


def _rgb_png(w: int, h: int, color=(20, 80, 160)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_make_thumb_bytes_shrinks_large_png():
    raw = _rgb_png(1200, 800)
    thumb = make_thumb_bytes(raw, max_edge=320)
    assert thumb is not None
    assert thumb[:2] == b"\xff\xd8"
    assert len(thumb) < len(raw)
    out = Image.open(BytesIO(thumb))
    assert max(out.size) <= 320


def test_read_image_variant_caches_thumb(tmp_path):
    storage = LocalStorage(str(tmp_path))
    rel = "materials/demo/big.png"
    raw = _rgb_png(1000, 1000)
    storage.save(rel, raw)

    data1, mt1 = read_image_variant(storage, rel, thumb=True, max_edge=200)
    assert mt1 == "image/jpeg"
    assert data1[:2] == b"\xff\xd8"
    cache = thumb_cache_rel(rel, 200)
    assert storage.exists(cache)

    data2, mt2 = read_image_variant(storage, rel, thumb=True, max_edge=200)
    assert mt2 == "image/jpeg"
    assert data2 == data1

    original, omt = read_image_variant(storage, rel, thumb=False)
    assert original == raw
    assert "png" in omt
