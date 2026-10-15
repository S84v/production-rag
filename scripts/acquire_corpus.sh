#!/usr/bin/env bash
#
# Acquire and prepare the pinned FastAPI documentation corpus used by ingestion
# and evaluation. The raw Markdown is intentionally kept out of Git; this script
# reproduces it deterministically at the revision pinned in docs/corpus.md and
# in src/production_rag/corpus/preparation.py.
#
# The upstream documentation is MkDocs source that references runnable examples
# in docs_src/ and fastapi/ through include directives. The corpus written to
# data/raw/fastapi/ is the prepared plain Markdown: includes are expanded and
# MkDocs-only syntax is normalised. Preparation is deterministic and fails on
# unresolved includes or unhandled constructs.
#
# Requirements: git and the project environment (`uv sync`). Re-running the
# script is safe: the checkout is recreated and the destination corpus is
# rewritten; only files recorded in the previous preparation manifest are
# replaced.

set -euo pipefail

REVISION="244d66308d6c525f394d0c2ce32dabceb2ed262b"
REPOSITORY="https://github.com/fastapi/fastapi.git"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CHECKOUT_DIR="${REPO_ROOT}/data/tmp/fastapi-checkout"
DEST_DIR="${REPO_ROOT}/data/raw/fastapi"

rm -rf "${CHECKOUT_DIR}"
mkdir -p "$(dirname "${CHECKOUT_DIR}")"

git clone --filter=blob:none --no-checkout --quiet "${REPOSITORY}" "${CHECKOUT_DIR}"
git -C "${CHECKOUT_DIR}" sparse-checkout init --no-cone
git -C "${CHECKOUT_DIR}" sparse-checkout set \
  'docs/en/docs/**' \
  'docs_src/**' \
  'fastapi/**' \
  'LICENSE'

git -C "${CHECKOUT_DIR}" checkout --quiet "${REVISION}"

RESOLVED_REVISION="$(git -C "${CHECKOUT_DIR}" rev-parse HEAD)"

if [[ "${RESOLVED_REVISION}" != "${REVISION}" ]]; then
  echo "error: resolved revision ${RESOLVED_REVISION} does not match pin ${REVISION}" >&2
  exit 1
fi

cd "${REPO_ROOT}"

uv run production-rag prepare-corpus \
  --checkout "${CHECKOUT_DIR}" \
  --dest "${DEST_DIR}"

echo "Prepared corpus at ${DEST_DIR} from ${REPOSITORY}@${REVISION}"
