# Corpus Provenance

## FastAPI Documentation Corpus

### Source

* **Project:** FastAPI
* **Repository:** https://github.com/fastapi/fastapi
* **Documentation:** https://fastapi.tiangolo.com/
* **Documentation source:** `docs/en/docs/`
* **License:** MIT
* **Pinned commit:** `244d66308d6c525f394d0c2ce32dabceb2ed262b`
* **Commit timestamp:** `2026-08-09T08:12:44Z`
* **Acquisition method:** Git sparse checkout from the official repository
* **Corpus retrieval date:** 2026-08-09

### Selected Documents

The initial corpus contains 16 Markdown documents from the FastAPI tutorial documentation:

```text
docs/en/docs/tutorial/first-steps.md
docs/en/docs/tutorial/path-params.md
docs/en/docs/tutorial/path-params-numeric-validations.md
docs/en/docs/tutorial/query-params.md
docs/en/docs/tutorial/query-params-str-validations.md
docs/en/docs/tutorial/body.md
docs/en/docs/tutorial/body-fields.md
docs/en/docs/tutorial/body-nested-models.md
docs/en/docs/tutorial/response-model.md
docs/en/docs/tutorial/response-status-code.md
docs/en/docs/tutorial/dependencies/index.md
docs/en/docs/tutorial/dependencies/sub-dependencies.md
docs/en/docs/tutorial/handling-errors.md
docs/en/docs/tutorial/middleware.md
docs/en/docs/tutorial/security/first-steps.md
docs/en/docs/tutorial/security/oauth2-jwt.md
```

### Selection Rationale

The initial subset was intentionally kept small to make the first ingestion and retrieval implementation easy to inspect and debug.

The documents cover several distinct FastAPI concepts:

* path parameters
* query parameters
* request bodies
* nested request models
* response models
* response status codes
* dependency injection
* error handling
* middleware
* authentication and OAuth2/JWT

The corpus can later be expanded to the remaining FastAPI tutorial documentation without requiring changes to the ingestion architecture.

### Reproducibility

The corpus is pinned to a specific Git commit rather than the repository's moving default branch.

To reproduce the source checkout:

```bash
git clone --filter=blob:none --no-checkout \
  https://github.com/fastapi/fastapi.git /tmp/fastapi-corpus

cd /tmp/fastapi-corpus

git sparse-checkout init --no-cone

git sparse-checkout set 'docs/en/docs/tutorial/**/*.md'

git checkout 244d66308d6c525f394d0c2ce32dabceb2ed262b
```

The selected files are copied into:

```text
data/raw/fastapi/
```

For a one-command, reproducible acquisition of exactly these 16 files, run:

```bash
./scripts/acquire_corpus.sh
```

The script downloads the pinned revision from the official upstream raw-file URLs
and writes them under `data/raw/fastapi/`. It is idempotent and fails on any HTTP
error, so a missing or moved file cannot be silently skipped.

The raw and processed corpus directories are intentionally excluded from Git.

### Evaluation labels

Retrieval evaluation labels reference this corpus by content, not by database
identifier. Each label anchors a `source_uri` relative to
`data/raw/fastapi/` (for example `filesystem://path-params.md`) to a verbatim
snippet. Changing the pinned revision or the selected documents can invalidate
anchors; the anchor resolution check over the local corpus (see
`tests/test_anchors.py`) is expected to be re-run after any corpus change, and a
new baseline recorded rather than overwriting the previous one.
