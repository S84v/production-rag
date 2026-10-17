# Architecture

DocAssist is a Retrieval-Augmented Generation (RAG) service. A FastAPI backend
answers natural-language questions about an indexed documentation corpus; the
retrieved passages ground the answer and are returned to the client as
inspectable sources.

This document describes how the system is put together. The HTTP contract lives
in [`api.md`](api.md), configuration in [`configuration.md`](configuration.md),
the corpus in [`corpus.md`](corpus.md), and the production deployment in
[`deployment.md`](deployment.md).

## Components

| Area | Location | Responsibility |
| --- | --- | --- |
| API | `src/production_rag/api/`, `main.py` | FastAPI app: `POST /query`, `GET /health`, request validation, collection allowlist, rate limiting, CORS |
| Ingestion | `ingestion/`, `services/document_ingestion.py`, `services/batch_ingestion.py` | Filesystem discovery, SHA-256 hashing, chunking, document versioning |
| Embeddings | `services/embedding.py` | Encode chunks and queries with `BAAI/bge-small-en-v1.5` |
| Persistence | `models/`, `repositories/`, `alembic/` | PostgreSQL is authoritative for metadata and chunk text |
| Vector search | `services/qdrant.py` | Qdrant stores vectors for similarity search |
| Retrieval | `services/retrieval.py`, `repositories/retrieval.py` | Query embedding, Qdrant search, PostgreSQL hydration |
| Generation | `services/rag.py`, `services/llm.py` | Context construction and DeepSeek streaming |
| Corpus | `corpus/preparation.py` | Deterministic preparation of the pinned corpus |
| Observability | `telemetry.py` | OpenTelemetry instrumentation |
| Frontend | `frontend/` | React single-page application |

## End-to-end flow

```text
                     ┌──────────────────────┐
                     │   Markdown corpus    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │  FilesystemSource    │
                     │  SHA-256 hashing     │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │   MarkdownChunker    │
                     │ headings + code      │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │     PostgreSQL       │
                     │ metadata + chunks    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │   EmbeddingService   │
                     │ BGE-small-en-v1.5    │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │        Qdrant        │
                     │    vector storage    │
                     └──────────┬───────────┘
                                │
                          query │
                                ▼
┌──────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│    Client    │ ───► │  RetrievalService    │ ───► │      RAGService      │
└──────────────┘      │ embedding → search   │      │ context + generation │
                      │ → hydration          │      └──────────┬───────────┘
                      └──────────────────────┘                 │
                                                                ▼
                                                   ┌──────────────────────┐
                                                   │  DeepSeek API        │
                                                   │  async streaming     │
                                                   └──────────┬───────────┘
                                                              │
                                                              ▼
                                                   ┌──────────────────────┐
                                                   │  FastAPI /query      │
                                                   │  NDJSON stream       │
                                                   └──────────────────────┘
```

## Persistence boundary

PostgreSQL is the authoritative store for application metadata; Qdrant is
responsible for vector similarity search. Qdrant payloads are **not** treated as
the metadata source of truth.

Identity relationships:

```text
Application collection → Qdrant collection
Chunk                  → Embedding
Embedding.id           → Qdrant point ID
```

Qdrant search returns embedding IDs and similarity scores; the application then
hydrates the corresponding chunk and document metadata from PostgreSQL. Results
that cannot be hydrated are excluded.

### Data model

```text
Collection
    └── Document
          └── DocumentVersion
                └── Chunk
                      └── Embedding
```

Document identity (a stable `source_uri`) is separated from document versions.
Embeddings are their own entity, recording the chunk, model name, model version,
and dimensions, so embedding identity and versioning stay explicit (see
[ADR-002](adr/002-embeddings-as-separate-domain-entity.md)). Collections map to
independent Qdrant collections ([ADR-001](adr/001-multi-collection-workspaces.md)).

## Ingestion pipeline

Markdown is parsed structurally with `markdown-it-py` rather than split at
arbitrary character boundaries; chunks preserve heading hierarchy, heading paths,
code blocks, and ordering (see
[ADR-003](adr/003-structure-aware-markdown-ingestion.md)). The default maximum
chunk size is about 4,000 characters.

Ingestion is idempotent: documents are identified by SHA-256 content hash, so
re-ingesting unchanged content does not create a new document version. The flow
is `FilesystemSource → BatchIngestionService → DocumentIngestionService →
PostgreSQL → EmbeddingService → Qdrant`. Embedding work is skipped when both the
embedding record and its Qdrant point already exist, and is repaired (reusing the
existing embedding id) when only the point is missing.

## Retrieval

```text
User query
    ↓
BGE query embedding
    ↓
Qdrant similarity search
    ↓
Embedding IDs + similarity scores
    ↓
PostgreSQL hydration (latest document version)
    ↓
Chunk + source metadata
    ↓
Ranked RetrievalResult objects
```

Only the requested number of vector results is retrieved. Retrieval is scoped by
collection and filtered to the latest version of each document, matching the
evaluation.

BGE is a bi-encoder: it embeds the query and the documents independently and
ranks by vector similarity. There is currently **no reranker**; retrieval quality
and its measurement are documented under [`evaluation/`](evaluation/).

## Generation and streaming

`RAGService` composes retrieval and generation:

1. retrieve relevant chunks,
2. record retrieval latency,
3. build the context within the configured budget,
4. send the question and context to DeepSeek,
5. stream generated text,
6. report total latency.

Generation is instructed to use only the retrieved context and to state when the
context does not contain enough information. The answer is streamed to the client
as newline-delimited JSON (NDJSON) with `sources`, `text`, and a single terminal
`complete` or `error` event. The exact event contract is in [`api.md`](api.md).

## Corpus preparation and vector-store consistency

The FastAPI documentation is acquired from a pinned revision and prepared
deterministically (MkDocs includes expanded, generated reference excluded); the
authoritative vector set is the embeddings of the latest version of each document
produced by the active model. Runtime retrieval, evaluation, and reconciliation
share that definition. See [ADR-006](adr/006-corpus-preparation-and-vector-store-consistency.md)
and [`corpus.md`](corpus.md).

## Application lifecycle

The FastAPI application creates a single `RAGService` (and its Qdrant and
DeepSeek clients) during startup and closes them on shutdown, so a long-lived
client is not created per request. `/health` is a shallow liveness check and does
not verify PostgreSQL, Qdrant, DeepSeek, or the embedding model.

## Observability

FastAPI is instrumented with OpenTelemetry, and the RAG pipeline creates a
dedicated `rag.generate` span recording the collection, retrieval limit,
retrieved and context chunk counts, retrieval latency, and total RAG latency. The
development configuration exports spans through the console exporter.

## Deployment shape

The deployed system runs the backend on Cloud Run and serves the static frontend
from Firebase Hosting; PostgreSQL (Neon), Qdrant Cloud, and DeepSeek remain
external managed services. See [`deployment.md`](deployment.md).
