# Production RAG

A production-oriented Retrieval-Augmented Generation (RAG) system built with FastAPI, PostgreSQL, Qdrant, Sentence Transformers, and DeepSeek.

The project focuses on the engineering problems that appear when moving beyond a basic RAG prototype: document versioning, idempotent ingestion, structure-aware chunking, vector/metadata separation, PostgreSQL hydration, lifecycle management, evaluation, streaming responses, and observability.

## Overview

The system ingests Markdown documentation, converts it into structure-aware chunks, generates embeddings, stores metadata in PostgreSQL and vectors in Qdrant, retrieves relevant context, and generates an answer using a DeepSeek-compatible LLM API.

The current evaluation corpus is the FastAPI documentation.

### Request flow

```text
                         ┌──────────────────────┐
                         │      Markdown        │
                         │       Corpus         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ FilesystemSource     │
                         │ SHA-256 content hash │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ MarkdownChunker      │
                         │ headings + code      │
                         │ structure metadata   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    PostgreSQL        │
                         │ documents            │
                         │ versions             │
                         │ chunks               │
                         │ embeddings metadata  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ EmbeddingService     │
                         │ BGE-small-en-v1.5    │
                         │ 384 dimensions       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       Qdrant         │
                         │   vector storage     │
                         └──────────┬───────────┘
                                    │
                              query │
                                    ▼
┌──────────────┐          ┌──────────────────────┐
│   Client     │ ───────► │   RetrievalService   │
└──────────────┘          │ embed → search →     │
                          │ PostgreSQL hydration │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │     RAGService       │
                          │ retrieval + prompt   │
                          │ + generation         │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │     DeepSeek LLM     │
                          │      streaming       │
                          └──────────┬───────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ FastAPI /query       │
                          │ NDJSON stream        │
                          └──────────────────────┘
```

## Why this architecture?

This project intentionally keeps the architecture simple while making the persistence boundaries explicit.

### PostgreSQL owns metadata

PostgreSQL stores:

* collections
* documents
* document versions
* chunks
* embedding metadata

It is the source of truth for document and chunk metadata.

### Qdrant owns vectors

Qdrant stores the actual embedding vectors used for similarity search.

The application maps:

```text
Application Collection → Qdrant Collection
Chunk                  → Embedding
Embedding.id           → Qdrant point ID
```

Retrieval does not treat Qdrant payloads as the authoritative document store. Qdrant identifies relevant vectors, after which PostgreSQL hydrates the corresponding chunk metadata.

This keeps the responsibilities of the two persistence systems clear.

## Tech stack

| Component            | Technology                             |
| -------------------- | -------------------------------------- |
| Language             | Python 3.12+                           |
| API                  | FastAPI                                |
| Database             | PostgreSQL 17                          |
| Vector database      | Qdrant                                 |
| Cache/infrastructure | Redis                                  |
| ORM                  | SQLAlchemy 2                           |
| Migrations           | Alembic                                |
| Embeddings           | `BAAI/bge-small-en-v1.5`               |
| LLM                  | DeepSeek API via OpenAI-compatible SDK |
| Markdown parsing     | markdown-it-py                         |
| Evaluation           | DeepEval + custom retrieval evaluation |
| Observability        | OpenTelemetry                          |
| Testing              | pytest                                 |
| Linting/formatting   | Ruff                                   |
| Package management   | uv                                     |
| Infrastructure       | Docker Compose                         |

## Key engineering features

### Structure-aware Markdown chunking

Markdown is parsed structurally rather than being split using arbitrary character boundaries.

Chunks preserve information such as:

* heading hierarchy
* heading path
* code blocks
* chunk ordering
* document/version relationships

The default chunk size is approximately 4,000 characters.

This is particularly useful for technical documentation where headings and code examples provide important retrieval context.

### Idempotent ingestion

Documents are identified using SHA-256 content hashes.

Re-ingesting an unchanged document does not create unnecessary new document versions.

The ingestion pipeline is organized around:

```text
FilesystemSource
       ↓
BatchIngestionService
       ↓
DocumentIngestionService
       ↓
PostgreSQL
       ↓
EmbeddingService
       ↓
Qdrant
```

### Versioned document model

The database separates:

```text
Collection
   └── Document
         └── DocumentVersion
               └── Chunk
                     └── Embedding
```

This allows document identity and document content/version identity to remain separate.

### Retrieval with PostgreSQL hydration

The retrieval pipeline is:

```text
User query
    ↓
BGE embedding
    ↓
Qdrant similarity search
    ↓
Embedding IDs / chunk IDs
    ↓
PostgreSQL hydration
    ↓
Ranked RetrievalResult objects
```

This avoids coupling the application to Qdrant payloads for authoritative metadata.

### Streaming generation

The LLM integration uses the OpenAI Python SDK against DeepSeek's OpenAI-compatible API.

Generation is streamed asynchronously rather than waiting for the complete answer before returning it.

### FastAPI lifecycle management

A single `RAGService` is created during application startup and closed during shutdown.

This keeps long-lived resources such as the LLM and vector-store clients under explicit application lifecycle management.

### OpenTelemetry tracing

The application instruments FastAPI and the RAG pipeline with OpenTelemetry.

RAG-level telemetry includes information such as:

* collection
* retrieval limit
* retrieved chunk count
* retrieval latency
* total RAG latency

The current configuration exports spans to the console, making the tracing behavior easy to inspect during development.

## Getting started

### Requirements

Install:

* Python 3.12+
* uv
* Docker and Docker Compose

Clone the repository and enter the project directory.

Install dependencies:

```bash
uv sync
```

### Environment configuration

Create the local environment file:

```bash
cp .env.example .env
```

Configure the required application settings.

The project uses:

```text
PostgreSQL → localhost:5432
Qdrant     → localhost:6333
Redis      → localhost:6379
```

The DeepSeek API key should be configured locally and must not be committed to the repository.

### Start infrastructure

Start PostgreSQL, Qdrant, and Redis:

```bash
docker compose up -d
```

Check the running services:

```bash
docker compose ps
```

### Run database migrations

Apply the current Alembic migrations:

```bash
uv run alembic upgrade head
```

## Ingest a corpus

The project provides a CLI for Markdown ingestion.

For example:

```bash
uv run production-rag ingest \
  --path data/raw/fastapi \
  --collection fastapi
```

The command:

1. Creates the application collection if necessary.
2. Discovers Markdown files.
3. Computes content hashes.
4. Creates document/version records.
5. Chunks the Markdown documents.
6. Generates embeddings.
7. Persists embedding metadata.
8. Stores vectors in Qdrant.

The CLI reports the number of discovered documents, new documents, processed chunks, and persisted embeddings.

## Query the RAG system

### CLI

```bash
uv run production-rag query \
  "How do I create a FastAPI application?" \
  --collection fastapi \
  --limit 5
```

The CLI prints the generated answer followed by the retrieved sources.

### API

Start the FastAPI application:

```bash
uv run uvicorn production_rag.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Query endpoint:

```bash
curl -N -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I create a FastAPI application?",
    "collection": "fastapi",
    "limit": 5
  }'
```

The endpoint returns an NDJSON stream containing retrieval sources, generated text, and completion information.

A typical response is conceptually:

```json
{"type":"sources","sources":[...]}
{"type":"text","text":"..."}
{"type":"complete","retrieval_time_ms":...,"total_time_ms":...}
```

The exact event payload is defined by the API schemas.

### Request validation

The API validates requests before starting the response stream.

Examples include:

* empty queries → `422`
* invalid retrieval limits → `422`
* missing required fields → `422`
* malformed JSON → `422`
* nonexistent collections → `404`

Valid requests stream results using `application/x-ndjson`.

## Evaluation

The project includes both retrieval and generation evaluation.

The current retrieval evaluation uses 24 FastAPI documentation examples.

The primary retrieval precision metric is intentionally **document-level Precision@K** rather than chunk-level precision. This avoids over-penalizing a retrieval system when multiple relevant chunks belong to the same source document.

### Retrieval baseline

|  K | Precision@K | Recall@K |  Hit@K |    MRR |
| -: | ----------: | -------: | -----: | -----: |
|  1 |      0.4167 |   0.3264 | 0.4167 | 0.4167 |
|  3 |      0.1806 |   0.4028 | 0.4583 | 0.4375 |
|  5 |      0.1500 |   0.5417 | 0.6250 | 0.4750 |
| 10 |      0.0833 |   0.6250 | 0.7083 | 0.4889 |
| 20 |      0.0521 |   0.7569 | 0.8333 | 0.4991 |

Detailed evaluation artifacts are available under:

```text
docs/evaluation/
data/evaluation/
```

The project also contains generation evaluation using DeepEval.

## Testing

Run the test suite:

```bash
uv run pytest -q
```

For the telemetry-enabled test environment, running without pytest's output capture can be useful:

```bash
uv run pytest -q -s
```

Run Ruff:

```bash
uv run ruff check .
```

The test suite covers:

* API behavior
* request validation
* health endpoint
* Markdown chunking
* filesystem ingestion
* document/version persistence
* repositories
* embeddings
* Qdrant behavior
* retrieval
* LLM integration
* RAG orchestration
* evaluation
* lifecycle management
* application settings

## Project structure

```text
production-rag/
├── alembic/
│   └── migrations
├── data/
│   ├── evaluation/
│   └── raw/
├── docs/
│   ├── adr/
│   ├── evaluation/
│   └── corpus.md
├── src/
│   └── production_rag/
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── evaluation/
│       ├── ingestion/
│       ├── models/
│       ├── repositories/
│       ├── retrieval/
│       ├── schemas/
│       ├── services/
│       ├── telemetry.py
│       └── main.py
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## Design decisions

Important architectural decisions are documented as ADRs under:

```text
docs/adr/
```

These documents capture decisions around areas such as:

* persistence boundaries
* vector storage
* retrieval architecture
* selective technology choices

The project intentionally avoids introducing large orchestration frameworks where they do not provide enough value.

In particular, ingestion does not depend on LangChain.

## Current scope

The project is intentionally designed as a production-oriented portfolio system rather than a complete SaaS platform.

Implemented capabilities include:

* [x] Markdown ingestion
* [x] Structure-aware chunking
* [x] Content-hash-based idempotency
* [x] Document versioning
* [x] PostgreSQL persistence
* [x] Qdrant vector storage
* [x] Embedding generation
* [x] PostgreSQL retrieval hydration
* [x] Similarity retrieval
* [x] DeepSeek generation
* [x] Streaming RAG responses
* [x] CLI
* [x] FastAPI API
* [x] Request validation
* [x] Lifecycle management
* [x] Retrieval evaluation
* [x] Generation evaluation
* [x] OpenTelemetry instrumentation
* [x] Automated tests
* [x] Ruff linting

## Deliberately out of scope

The architecture does not currently introduce distributed infrastructure simply for the sake of appearing "production ready."

Examples of intentionally avoided complexity include:

* Celery-based task orchestration
* Kafka/event streaming
* Outbox patterns
* Kubernetes
* distributed transactions
* unnecessary caching layers
* large RAG frameworks for ingestion

These can be introduced later if an actual requirement justifies them.

## Roadmap

The next engineering priorities are focused on hardening rather than continuously adding features.

Potential future work includes:

1. Improve operational documentation.
2. Tighten ingestion/vector lifecycle consistency.
3. Expand evaluation methodology and datasets.
4. Improve failure handling around external services.
5. Add targeted production-hardening tests.
6. Revisit caching only if profiling demonstrates a meaningful need.
7. Add deployment-oriented configuration if the system is eventually deployed.

The guiding principle is to prefer measurable improvements over architectural complexity.

## Project status

The core RAG vertical slice is functional:

```text
Corpus
  → ingestion
  → chunking
  → embeddings
  → Qdrant
  → retrieval
  → PostgreSQL hydration
  → DeepSeek generation
  → streaming API
  → evaluation
  → telemetry
```

The project is currently in the **evaluation and production-hardening stage**, rather than the initial implementation stage.
