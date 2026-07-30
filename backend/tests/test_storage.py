"""Unit tests for LocalStorage and OssStorage (mocked OSS)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.storage import LocalStorage, OssStorage, get_storage
from app.core.config import clear_settings_cache


def test_local_storage_save_read_roundtrip(tmp_path: Path):
    store = LocalStorage(str(tmp_path / "up"))
    rel = store.save("materials/1/a.txt", b"hello")
    assert rel == "materials/1/a.txt"
    assert store.read(rel) == b"hello"
    assert store.exists(rel)
    assert not store.exists("missing.bin")


def test_oss_object_key_prefix():
    with patch("oss2.Auth"), patch("oss2.Bucket") as Bucket:
        bucket = MagicMock()
        Bucket.return_value = bucket
        store = OssStorage(
            endpoint="oss-cn-shanghai.aliyuncs.com",
            access_key_id="id",
            access_key_secret="secret",
            bucket_name="my-bucket",
            prefix="one-class/uploads",
        )
        assert store.object_key("materials/1/x.jpg") == "one-class/uploads/materials/1/x.jpg"


def test_oss_save_puts_object():
    with patch("oss2.Auth"), patch("oss2.Bucket") as Bucket:
        bucket = MagicMock()
        Bucket.return_value = bucket
        store = OssStorage(
            endpoint="https://oss-cn-shanghai.aliyuncs.com",
            access_key_id="id",
            access_key_secret="secret",
            bucket_name="b",
            prefix="one-class/uploads/",
        )
        rel = store.save("posters/abc.png", b"PNGDATA")
        assert rel == "posters/abc.png"
        bucket.put_object.assert_called_once_with("one-class/uploads/posters/abc.png", b"PNGDATA")


def test_oss_read_fallback_local(tmp_path: Path):
    import oss2

    local_root = tmp_path / "uploads"
    local = LocalStorage(str(local_root))
    local.save("materials/9/old.jpg", b"legacy")

    with patch("oss2.Auth"), patch("oss2.Bucket") as Bucket:
        bucket = MagicMock()
        Bucket.return_value = bucket
        bucket.get_object.side_effect = oss2.exceptions.NoSuchKey(
            status=404, headers={}, body=b"", details={}
        )
        store = OssStorage(
            endpoint="oss-cn-shanghai.aliyuncs.com",
            access_key_id="id",
            access_key_secret="secret",
            bucket_name="b",
            prefix="one-class/uploads/",
            local_fallback_root=str(local_root),
        )
        assert store.read("materials/9/old.jpg") == b"legacy"


def test_get_storage_oss_requires_config(monkeypatch):
    clear_settings_cache()
    monkeypatch.setenv("STORAGE_BACKEND", "oss")
    monkeypatch.setenv("OSS_ENDPOINT", "")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "")
    monkeypatch.setenv("OSS_BUCKET", "")
    clear_settings_cache()
    with pytest.raises(RuntimeError, match="缺少配置"):
        get_storage()
    clear_settings_cache()


def test_get_storage_local_default(monkeypatch, tmp_path: Path):
    clear_settings_cache()
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "d"))
    clear_settings_cache()
    store = get_storage()
    assert isinstance(store, LocalStorage)
    store.save("t.bin", b"1")
    assert store.read("t.bin") == b"1"
    clear_settings_cache()
