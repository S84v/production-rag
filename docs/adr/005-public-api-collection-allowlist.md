# ADR-005: Public API Collection Allowlist

- **Status:** Accepted
- **Date:** 2026-10-14

## Context

ADR-001 makes collections first-class domain concepts and explicitly notes that
authorization and multi-tenant security are not implemented as part of that
decision. The public `POST /query` endpoint, however, accepted any collection
name and only required that the collection exist in Qdrant, exposing every
ingested collection to anonymous callers.

## Decision

The public API enforces a fixed allowlist of collections.

- The allowlist is configured with the `ALLOWED_COLLECTIONS` environment variable
  (comma-separated) and defaults to `fastapi`.
- The allowlist is checked in the API layer before any Qdrant lookup.
- Disallowed and nonexistent collections both return `404` with the same detail
  message, so the API does not reveal whether a collection exists.

Ingestion, retrieval, the CLI, and evaluation remain able to operate on any
collection. The allowlist constrains only the public API boundary; it does not
change the multi-collection domain model from ADR-001.

## Rationale

This is the smallest control that limits what the public endpoint can expose
while preserving the multi-collection architecture. It reuses the existing
configuration infrastructure and adds no dependencies, rate limiting, or
deployment concerns.

## Consequences

- Making a collection publicly queryable requires a configuration change and a
  restart.
- The allowlist is a coarse, collection-level control. It is not authentication
  or per-user authorization.
- An explicitly empty `ALLOWED_COLLECTIONS` denies all collections.
