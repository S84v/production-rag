from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source: str
    source_uri: str
    content: str
    content_hash: str
    title: str | None
    source_revision: str | None
