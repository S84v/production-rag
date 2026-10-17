# Evaluation

DocAssist evaluates two things: whether retrieval finds the right chunks, and
(historically) whether the generated answer is grounded in them.

Results are recorded as **dated artifacts** and never overwritten. This page
indexes them and states clearly which are current and which are historical.

## Dataset

`data/evaluation/fastapi.json` — 29 examples. Each example has a question, a
reference answer, and one or more **content anchors** under `relevant_chunks`:

```json
{ "source_uri": "filesystem://path-params.md", "snippet": "<verbatim excerpt>" }
```

Anchors are resolved to current chunk IDs at evaluation time by matching the
whitespace-normalized snippet against chunks from the same `source_uri`, so labels
survive re-chunking and corpus changes. A snippet that matches no chunk or more
than one chunk raises an error rather than silently dropping or guessing a label
(see `src/production_rag/evaluation/anchors.py`).

## Retrieval evaluation (current)

Retrieval evaluation is chunk-level and reports Precision@K, Recall@K, Hit@K, and
MRR.

**Current reproducible baseline:** the anchor-based baseline recorded on
**2026-10-16** over all 29 examples, with no reranker. Methodology and the full
table are in [`retrieval_baseline.md`](retrieval_baseline.md); the artifact is:

```text
data/evaluation/results/fastapi-retrieval-baseline-2026-10-16.json
```

At the application's default retrieval depth (`K = 5`):

| Retrieval depth | Precision | Recall | Hit rate | MRR |
| --------------: | --------: | -----: | -------: | --: |
| 5 | 0.1310 | 0.5977 | 0.6552 | 0.5316 |

`K = 10` and `K = 20` are diagnostic candidate-depth measurements that the
application does not use.

Run it against a local corpus:

```bash
uv run python -m production_rag.evaluation.retrieval \
  --dataset data/evaluation/fastapi.json --collection fastapi --k 5
```

This requires PostgreSQL, Qdrant, and the cached embedding model, with the corpus
ingested (`./scripts/acquire_corpus.sh` then `uv run production-rag ingest ...`).

### Legacy baseline (non-reproducible, historical)

`retrieval_baseline.md` also preserves an older baseline produced with
**UUID-based** labels over 24 examples. Those labels reference runtime `uuid4`
chunk IDs and cannot be reproduced from a clean rebuild. They are kept for
historical reference only and **must not** be compared against the anchor-based
results.

## Generation / answer evaluation (historical)

The generation evaluation runs the full end-to-end pipeline and captures each
answer for manual review. Two generation-related artifacts exist, both recorded
**before the corpus expansion** and therefore over **24 examples** rather than the
current 29:

- [`generation_results.md`](generation_results.md) — full generated answers,
  retrieved sources, and timings for manual comparison against the reference
  answers. It includes examples where the model correctly reported that the
  retrieved context did not contain the answer; these predate the expanded corpus
  (in particular the corpus items that added the FastAPI code examples).
- `data/evaluation/results/fastapi-answer-baseline-2026-09-01.json` — a DeepEval
  answer-quality run (contextual recall/precision, answer relevancy, faithfulness)
  judged by `deepseek-chat` at commit `1ab7585`.

These are **historical**: they were produced from an earlier corpus and an earlier
answer/judge configuration. Treat them as provenance, not as current metrics, and
do not mix them with the current retrieval baseline. Refreshing them requires live
DeepSeek calls plus PostgreSQL, Qdrant, and the cached model, and is not part of
documentation changes.

## Adding a baseline

Record a new run as a new dated artifact under
`data/evaluation/results/` rather than overwriting an existing one, and update
this index and the relevant methodology page.
