# ADR-002: Model Embeddings as a Separate Domain Entity

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

A document chunk may have multiple vector representations over the lifetime
of the system.

Embedding models can change because of model upgrades, retrieval experiments,
quality improvements, or migration requirements.

The storage representation used by a vector database does not necessarily
match the application's domain model.

## Decision

Embeddings are modeled as a separate domain entity from chunks.

An embedding represents a vector generated from a specific source chunk using a
specific embedding model and version.

The application domain will not be tightly coupled to Qdrant's internal
storage representation.

## Rationale

Separating embeddings enables:

- multiple embedding models
- embedding versioning
- embedding migrations
- retrieval experiments
- A/B testing
- independent evaluation of embedding strategies

It also keeps the domain model independent of the selected vector database.

## Consequences

Embedding metadata must identify the relevant model/version and source data.

Qdrant will store the representation required for efficient vector search,
while PostgreSQL can retain durable metadata needed by the application.

The application must maintain consistency between relational metadata and
vector-store state as ingestion evolves.
