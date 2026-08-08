# ADR-001: Support Multiple Collections / Workspaces

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

The RAG platform is intended to support multiple independent collections or
workspaces rather than operating as a single global document corpus.

A collection/workspace provides a logical boundary around documents and their
associated retrieval data.

## Decision

Collections/workspaces are first-class domain concepts in the system.

Documents, chunks, ingestion jobs, and retrieval operations will be associated
with a collection/workspace where appropriate.

The architecture will preserve collection-level boundaries so that retrieval
can be isolated and metadata filtering can be applied consistently.

## Rationale

This provides a foundation for:

- retrieval isolation
- collection-level metadata filtering
- future authorization boundaries
- collection-specific retrieval configuration
- independent ingestion and lifecycle management
- future scalability

Authorization and multi-tenant security mechanisms are not implemented as part
of this decision. They can be introduced later without changing the fundamental
domain boundary.

## Consequences

The application and persistence models need to carry collection/workspace
identity where relevant.

Vector retrieval must also preserve this boundary through Qdrant payload
metadata or an equivalent mechanism.

The domain model therefore needs to treat collections/workspaces as explicit
entities rather than as an implicit property of documents.
