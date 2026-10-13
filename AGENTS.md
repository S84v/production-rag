# AGENTS.md — Production RAG

Behavioral instructions for AI agents working in this repository. Keep it short
and durable: detailed, task-specific information lives in the README,
`docs/adr/`, `docs/corpus.md`, `docs/evaluation/`, and the source/tests/config.
Verify those exist and still describe reality before relying on them. If your
work makes this file's guidance stale, update it in the same change; if it
conflicts with observed behavior, verify by read-only inspection. Flag unrelated
discrepancies separately rather than expanding the current task.

## Purpose and scale

Production RAG is a small public portfolio demo: a few recruiters per week,
arriving intermittently. Optimize for correctness, maintainability, reliability,
and low cost — not large-scale throughput or infrastructure sophistication.

- Prefer reusing suitable existing Google Cloud, Firebase, Neon, and DeepSeek
  resources. Hosted Qdrant is preferred, subject to verifying suitability and cost.
- Do not assume account access, quotas, credits, API balances, free-tier
  allowances, or billing status have been verified; these are not observable
  from the repository.
- Do not create duplicate projects or introduce paid services without a concrete
  justification and explicit operator approval.

## Architecture invariants

- **PostgreSQL is authoritative** for relational metadata and chunk content;
  **Qdrant stores vectors** for similarity search. Qdrant payloads are not the
  metadata source of truth.
- Ingestion (documents → versions → chunks → embeddings) feeds vector search;
  PostgreSQL hydrates retrieved results. Preserve these responsibilities unless
  a reviewed ADR changes them.
- The application, ingestion/evaluation CLI, React frontend, and local Docker
  Compose services exist today. Do not assume any deployment stage; verify
  current status from the repository's configuration and authorized evidence.
- Inspect the current code, config, and tests before asserting what does or does
  not exist. Do not treat gaps from past sessions as permanent facts; when a gap
  is fixed, update the relevant guidance so it stops reporting it.

Overview and setup: `README.md`. Accepted decisions: `docs/adr/`.

## Repository orientation

Main directories: `src/production_rag/` (API, ingestion, models, repositories,
services, evaluation), `alembic/` (migrations), `tests/`, `frontend/`, `docs/`,
and `data/` (corpus and evaluation artifacts; inspect `.gitignore` and
`git status` to determine what is actually tracked or ignored).
Treat this as orientation, not an inventory — inspect the current filesystem.
Update it only when a structural change would otherwise make it misleading;
routine file additions do not require edits.

## Environment and commands

- Use the project's configured Python, normally via `uv run` (or `.venv/bin/*`).
  Do not assume the system `python3` is the project interpreter.
- Verify the current `.python-version`, `pyproject.toml`, lockfile, and package
  scripts before making compatibility claims or running commands; a previously
  successful command is not proof it still works.
- Typical local cycle: `uv sync` → `docker compose up -d` → `uv run alembic
  upgrade head` → `uv run uvicorn production_rag.main:app --reload`; for the CLI,
  consult the README or run `uv run production-rag --help`. Frontend scripts live
  in `frontend/package.json`.
- Do not silently change toolchain pins or dependencies, or add new ones.
- Never claim a command or test passed unless it was run and its result observed.

## Testing

- Distinguish tests that run without services (fakes/mocks) from those requiring
  PostgreSQL, Qdrant, cached embedding models, credentials, or external APIs.
- Inspect current tests, fixtures, markers, and configuration before choosing
  which checks are safe to run; any such list is an initial reference, not a
  permanent inventory.
- Never point tests at a shared, staging, or production database or vector store.
- Do not call live generation APIs for routine testing.

## Workflow and permissions

**Plan → review → Build → inspect diff and tests → commit.**

- Keep changes small and reviewable; run relevant verification and read the diff
  before declaring completion.
- Inspect `git status` and preserve uncommitted user work before editing.
- Require explicit approval before committing, pushing, deploying, destructive
  Git/filesystem operations, or cloud and other external-state changes. Never
  mutate shared, staging, production, external, or unidentified databases or
  vector stores without approval. For local resources, verify locality and side
  effects, stay within the approved task, risk no unrelated data, and never
  infer "local" from a name or config example.

## Security and cost

- Never commit or print secrets, credentials, `.env` contents, API keys, tokens,
  connection strings, database dumps, or downloaded corpus data.
- Prefer the smallest change; avoid unnecessary dependencies, services,
  abstractions, and operational complexity.
- Obtain approval before meaningful cost, architecture, account, or
  external-state changes. Never assume a free tier covers usage.

## Public API safeguards

Before exposing the API publicly, verify that low-cost controls are implemented,
tested, and documented, and add any missing: request-length and retrieval
limits, a fixed collection allowlist, bounded generation output and context,
sensible timeouts, and proportionate scaling. Browser-side checks are not
enforcement.

- Evaluate rate limiting across **multiple Cloud Run instances**: an in-memory
  limiter is per-instance and does not provide a global limit.
- Do not add Redis, API Gateway, Cloud Armor, or similar without a concrete
  justification and operator approval.

## Corpus and evaluation

- Goal: comprehensive **English-language FastAPI** documentation, acquired
  reproducibly from the official repository at a **pinned revision**. Preserve
  attribution, license, and reproducibility. Keep raw corpus data out of Git;
  verify `.gitignore` and `git status` before handling it. See `docs/corpus.md`.
- Corpus contents, chunking, identifiers, and results change. Do not hard-code
  counts, file lists, revisions, or metrics in this file; verify the current
  manifest, acquisition process, identifiers, and chunking before changes.
- Prefer **stable, content-based evaluation labels** resolved to current IDs.
  Do not present old labels, results, or baselines as reproducible without
  re-running against a known corpus revision.
- Version evaluation baselines by date and configuration; never silently
  overwrite them. Methodology and results live under `docs/evaluation/` and
  `data/evaluation/`.

## Documentation

Update the relevant README, ADR, corpus, evaluation, or operational docs in the
same change whenever behavior, configuration, or architecture changes. Record
lasting architectural decisions as new ADRs; do not rewrite accepted ones.

## Code style

Use comments where they clarify non-obvious behavior, invariants, or design
trade-offs; avoid comments that merely restate the code.

## MCP tools (when available)

Verify availability and permissions in the active session; a tool's presence is
not permission to change external resources. Prefer local inspection first.

- **Context7** — current library/framework docs when compatibility is uncertain.
- **GitHub** — read-only by default (repository, history, search); any write
  requires explicit authorization and must follow the approval rules above.
- **Playwright** — browser verification against an app already running and safe.
- **Tavily** — fresh external research; public docs are not evidence of the
  operator's account state.

If a tool is unavailable, fall back to local inspection and say so.

## Working with the operator

Ask before anything that could cost money, expose data, or change external
state. Separate verified facts from assumptions, and surface unresolved decisions
rather than defaulting to choices with cost, security, or architectural impact.
