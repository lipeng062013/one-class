from pathlib import Path

from app.core.config import get_settings


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or get_settings().storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, data: bytes) -> str:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return relative_path.replace("\\", "/")

    def absolute_path(self, relative_path: str) -> Path:
        return self.root / relative_path

    def open_bytes(self, relative_path: str) -> bytes:
        return self.absolute_path(relative_path).read_bytes()

    def read(self, relative_path: str) -> bytes:
        return self.open_bytes(relative_path)

    def open(self, relative_path: str):
        return self.absolute_path(relative_path).open("rb")


def get_storage() -> LocalStorage:
    return LocalStorage()
