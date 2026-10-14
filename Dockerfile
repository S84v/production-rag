# syntax=docker/dockerfile:1

# Immutable Hugging Face revision for the baked embedding model. The runtime
# stage derives EMBEDDING_MODEL_REVISION from this argument.
ARG HF_MODEL_REVISION=5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

# ---- builder: resolve dependencies, build the project, bake the model ----
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    HF_HOME=/opt/hf

WORKDIR /app

# Install third-party dependencies first so this layer is cached across source
# changes. README.md is required by the uv_build backend (project.readme).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --extra cpu --no-dev --no-install-project

# Build and install the project as a wheel (non-editable) so the runtime image
# does not need the source tree.
COPY src ./src
RUN uv sync --frozen --extra cpu --no-dev --no-editable

# Bake the embedding model at the pinned revision; the runtime must never
# download it. onnx and the duplicate *.bin weights are unused by the
# safetensors-based PyTorch loader. HF_HUB_OFFLINE is enforced at runtime.
ARG HF_MODEL_REVISION
RUN .venv/bin/python -c "import os; from pathlib import Path; from huggingface_hub import snapshot_download; rev = os.environ['HF_MODEL_REVISION']; path = Path(snapshot_download(repo_id='BAAI/bge-small-en-v1.5', revision=rev, ignore_patterns=['onnx/*', '*.bin'])); assert path.name == rev, (path.name, rev); print('baked', path)"


# ---- runtime: minimal image with only what the API needs ----
FROM python:3.12-slim-bookworm AS runtime

# Re-declare so the runtime environment derives from the same revision the
# model was baked at.
ARG HF_MODEL_REVISION

# libgomp1 is the OpenMP runtime PyTorch needs; ca-certificates for TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

# EMBEDDING_MODEL_REVISION derives from the same argument used to bake the
# model, so the runtime loads exactly that revision.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    EMBEDDING_MODEL_REVISION=$HF_MODEL_REVISION \
    PORT=8080 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --from=builder --chown=appuser:appuser /opt/hf /opt/hf
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./

USER appuser

EXPOSE 8080

# A single worker avoids duplicating the embedding model in memory. exec makes
# uvicorn PID 1 so it receives SIGTERM for graceful shutdown.
CMD ["sh", "-c", "exec uvicorn production_rag.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
