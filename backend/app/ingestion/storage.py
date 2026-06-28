from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Protocol

from app.ingestion.contracts import SourceDocument


class RawStorageError(RuntimeError):
    pass


class RawDocumentStorage(Protocol):
    def store(self, document: SourceDocument) -> SourceDocument: ...


class MemoryRawStorage:
    """Bounded-test storage; production runs should use durable storage."""

    def __init__(self) -> None:
        self.documents: dict[str, bytes] = {}

    def store(self, document: SourceDocument) -> SourceDocument:
        if document.content_bytes is None:
            raise RawStorageError("content_bytes is required for memory storage")
        self.documents[document.content_sha256] = document.content_bytes
        return document.model_copy(
            update={
                "storage_uri": (
                    f"memory://{document.source_id}/{document.content_sha256}"
                )
            }
        )


class FilesystemRawStorage:
    """Content-addressed raw response storage for local/demo deployments."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, document: SourceDocument) -> SourceDocument:
        if document.content_bytes is None:
            raise RawStorageError("content_bytes is required for filesystem storage")
        actual_hash = hashlib.sha256(document.content_bytes).hexdigest()
        if actual_hash != document.content_sha256:
            raise RawStorageError("document hash changed before storage")

        target = self.path_for(document)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != document.content_bytes:
                raise RawStorageError("content-addressed storage collision")
        else:
            self._atomic_write(target, document.content_bytes)
        return document.model_copy(update={"storage_uri": target.as_uri()})

    def path_for(self, document: SourceDocument) -> Path:
        target = (
            self.root
            / document.source_id
            / document.content_sha256[:2]
            / f"{document.content_sha256}.bin"
        ).resolve()
        if self.root not in target.parents:
            raise RawStorageError("raw storage path escaped configured root")
        return target

    @staticmethod
    def _atomic_write(target: Path, content: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=".raw-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()
