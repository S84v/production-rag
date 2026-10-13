#!/usr/bin/env bash
#
# Fetch the pinned FastAPI documentation corpus used by the ingestion and
# evaluation tests. The raw Markdown is intentionally kept out of Git, so this
# script reproduces it deterministically at the revision pinned in
# docs/corpus.md. Re-running it is safe: each file is overwritten in place.

set -euo pipefail

REVISION="244d66308d6c525f394d0c2ce32dabceb2ed262b"
BASE_URL="https://raw.githubusercontent.com/fastapi/fastapi/${REVISION}/docs/en/docs/tutorial"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEST_DIR="${REPO_ROOT}/data/raw/fastapi"

FILES=(
  "first-steps.md"
  "path-params.md"
  "path-params-numeric-validations.md"
  "query-params.md"
  "query-params-str-validations.md"
  "body.md"
  "body-fields.md"
  "body-nested-models.md"
  "response-model.md"
  "response-status-code.md"
  "dependencies/index.md"
  "dependencies/sub-dependencies.md"
  "handling-errors.md"
  "middleware.md"
  "security/first-steps.md"
  "security/oauth2-jwt.md"
)

for file in "${FILES[@]}"; do
  mkdir -p "${DEST_DIR}/$(dirname "${file}")"
  curl --fail --silent --show-error --location \
    "${BASE_URL}/${file}" \
    --output "${DEST_DIR}/${file}"
done

echo "Acquired ${#FILES[@]} corpus files into ${DEST_DIR}"
