"""File storage: local disk or Aliyun OSS (private bucket, backend-proxied)."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class Storage(Protocol):
    def save(self, relative_path: str, data: bytes) -> str: ...

    def read(self, relative_path: str) -> bytes: ...

    def open_bytes(self, relative_path: str) -> bytes: ...

    def exists(self, relative_path: str) -> bool: ...


def _norm_rel(relative_path: str) -> str:
    return relative_path.replace("\\", "/").lstrip("/")


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, data: bytes) -> str:
        rel = _norm_rel(relative_path)
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return rel

    def absolute_path(self, relative_path: str) -> Path:
        return self.root / _norm_rel(relative_path)

    def open_bytes(self, relative_path: str) -> bytes:
        return self.absolute_path(relative_path).read_bytes()

    def read(self, relative_path: str) -> bytes:
        return self.open_bytes(relative_path)

    def open(self, relative_path: str):
        return self.absolute_path(relative_path).open("rb")

    def exists(self, relative_path: str) -> bool:
        return self.absolute_path(relative_path).is_file()


class OssStorage:
    """Upload/download via Aliyun OSS. Optional local fallback on read for legacy files."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        prefix: str = "one-class/uploads/",
        local_fallback_root: str | None = None,
    ) -> None:
        import oss2

        endpoint = endpoint.strip()
        if endpoint.startswith("https://"):
            endpoint = endpoint[len("https://") :]
        elif endpoint.startswith("http://"):
            endpoint = endpoint[len("http://") :]

        self._prefix = prefix if prefix.endswith("/") else f"{prefix}/"
        self._prefix = self._prefix.lstrip("/")
        auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(auth, endpoint, bucket_name)
        self._local: LocalStorage | None = None
        if local_fallback_root:
            self._local = LocalStorage(local_fallback_root)

    def object_key(self, relative_path: str) -> str:
        return f"{self._prefix}{_norm_rel(relative_path)}"

    def save(self, relative_path: str, data: bytes) -> str:
        rel = _norm_rel(relative_path)
        key = self.object_key(rel)
        self._bucket.put_object(key, data)
        return rel

    def read(self, relative_path: str) -> bytes:
        import oss2

        rel = _norm_rel(relative_path)
        key = self.object_key(rel)
        try:
            result = self._bucket.get_object(key)
            return result.read()
        except oss2.exceptions.NoSuchKey as exc:
            if self._local and self._local.exists(rel):
                logger.info("OSS miss, local fallback for %s", rel)
                return self._local.read(rel)
            raise FileNotFoundError(rel) from exc
        except oss2.exceptions.OssError as exc:
            if self._local and self._local.exists(rel):
                logger.info("OSS error (%s), local fallback for %s", exc, rel)
                return self._local.read(rel)
            raise

    def open_bytes(self, relative_path: str) -> bytes:
        return self.read(relative_path)

    def open(self, relative_path: str):
        return BytesIO(self.read(relative_path))

    def exists(self, relative_path: str) -> bool:
        rel = _norm_rel(relative_path)
        key = self.object_key(rel)
        try:
            return bool(self._bucket.object_exists(key))
        except Exception:
            if self._local:
                return self._local.exists(rel)
            raise


def get_storage() -> Storage:
    settings = get_settings()
    backend = (settings.storage_backend or "local").strip().lower()
    if backend in ("", "local", "disk", "filesystem"):
        return LocalStorage(settings.storage_root)
    if backend == "oss":
        missing = [
            name
            for name, val in (
                ("OSS_ENDPOINT", settings.oss_endpoint),
                ("OSS_ACCESS_KEY_ID", settings.oss_access_key_id),
                ("OSS_ACCESS_KEY_SECRET", settings.oss_access_key_secret),
                ("OSS_BUCKET", settings.oss_bucket),
            )
            if not (val or "").strip()
        ]
        if missing:
            raise RuntimeError(
                "STORAGE_BACKEND=oss 但缺少配置: "
                + ", ".join(missing)
                + "。请在服务器 .env 中填写，参见 docs/ops-auto-deploy.md"
            )
        return OssStorage(
            endpoint=settings.oss_endpoint,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            bucket_name=settings.oss_bucket,
            prefix=settings.oss_upload_prefix or "one-class/uploads/",
            local_fallback_root=settings.storage_root,
        )
    raise RuntimeError(f"未知 STORAGE_BACKEND={settings.storage_backend!r}，请用 local 或 oss")
