import hashlib
from pathlib import Path

from production_rag.ingestion.source import SourceDocument


class FilesystemSource:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def acquire(self, path: Path) -> SourceDocument:
        resolved_path = path.resolve()

        if not resolved_path.is_relative_to(self.root):
            raise ValueError("path must be inside source root")

        content = resolved_path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        relative_path = resolved_path.relative_to(self.root)

        return SourceDocument(
            source="filesystem",
            source_uri=f"filesystem://{relative_path.as_posix()}",
            content=content,
            content_hash=content_hash,
            title=resolved_path.name,
            source_revision=str(resolved_path.stat().st_mtime_ns),
        )
