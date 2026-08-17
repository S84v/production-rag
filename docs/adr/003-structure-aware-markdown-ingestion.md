# ADR-003: Structure-Aware Markdown Ingestion

* **Status:** Accepted
* **Date:** 2026-08-17

## Context

The initial RAG corpus consists of technical documentation written in
Markdown, including documentation from FastAPI.

The documentation contains meaningful structure such as headings,
paragraphs, lists, fenced code blocks, and documentation-specific Markdown
constructs.

The corpus is expected to expand to include documentation from other software
projects such as Docker and Qdrant.

Generic character-based splitting does not preserve this structure and can
produce chunks that separate headings from their content or split code blocks
in undesirable places.

At the same time, implementing a Markdown parser within the application would
add unnecessary complexity and maintenance overhead.

## Decision

Markdown documents will be parsed using `markdown-it-py`.

The application will own the chunking policy rather than relying on a
framework-provided text splitter.

The ingestion flow will be:

```
Markdown document
    ↓
markdown-it-py
    ↓
structure-aware chunking
    ↓
ChunkData
    ↓
ChunkRepository
```

The chunker will produce deterministic, ordered chunks and preserve useful
document structure through chunk content and metadata.

Heading hierarchy will be preserved as metadata, and semantic document
boundaries will be preferred when creating chunks.

Code blocks will be treated as atomic blocks where possible and will not be
arbitrarily split when a suitable boundary is available.

The chunker will remain independent of PostgreSQL, SQLAlchemy, Qdrant,
embeddings, and LLMs.

## Rationale

Using `markdown-it-py` provides a mature Markdown parser without requiring the
project to maintain its own Markdown parsing logic.

Keeping the chunking policy within the application provides control over
retrieval-oriented behavior and makes chunking deterministic and independently
testable.

This also allows Markdown parsing to remain an implementation detail while
the rest of the ingestion pipeline works with application-defined chunk data.

## Consequences

The project has an additional dependency for Markdown parsing.

The application owns the chunking behavior and must maintain tests for its
chunking rules.

Markdown-specific behavior can be extended later if documentation sources use
additional syntax that requires special handling.

The same chunking interface can be reused as the documentation corpus expands
to other Markdown-based sources.
