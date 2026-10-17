# Architecture Decision Records

Accepted architectural decisions for DocAssist. Each record states its context,
decision, and consequences; accepted records are not rewritten.

| ADR | Title | Decision |
| --- | --- | --- |
| [ADR-001](001-multi-collection-workspaces.md) | Support Multiple Collections / Workspaces | Collections are first-class domain concepts, each mapping to an independent Qdrant collection |
| [ADR-002](002-embeddings-as-separate-domain-entity.md) | Model Embeddings as a Separate Domain Entity | Embeddings are modeled separately from chunks so model identity and versioning stay explicit |
| [ADR-003](003-structure-aware-markdown-ingestion.md) | Structure-Aware Markdown Ingestion | Markdown is parsed with `markdown-it-py` instead of being split at arbitrary boundaries |
| [ADR-004](004-selective-use-of-langchain.md) | Selective Use of LangChain | LangChain is adopted only where it adds clear value; the core ingestion pipeline does not depend on it |
| [ADR-005](005-public-api-collection-allowlist.md) | Public API Collection Allowlist | The public API enforces a fixed allowlist of collections |
| [ADR-006](006-corpus-preparation-and-vector-store-consistency.md) | Corpus Preparation and Vector-Store Consistency | The pinned corpus is prepared deterministically and the authoritative vector set is shared by retrieval, evaluation, and reconciliation |
