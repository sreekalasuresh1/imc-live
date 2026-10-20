"""Private storage boundary. Upload/download authorization arrives in Phase 4/5."""
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class Storage(Protocol):
    def put(self, data: bytes) -> str: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key):
        from uuid import UUID
        if str(UUID(key)) != key:
            raise ValueError('Invalid storage key')
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError('Invalid storage path')
        return path

    def put(self, data):
        self.root.mkdir(parents=True, exist_ok=True)
        key = str(uuid4())
        with self._path(key).open('xb') as output:
            output.write(data)
        return key

    def read(self, key):
        return self._path(key).read_bytes()

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)
