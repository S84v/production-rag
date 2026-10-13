# Retrieval Evaluation Baseline

## Labeling methodology

Retrieval labels are **content anchors**, not chunk identifiers. Each example
lists one or more anchors of the form:

```json
{ "source_uri": "filesystem://path-params.md", "snippet": "<verbatim excerpt>" }
```

An anchor is resolved to the current chunk ID at evaluation time by matching the
whitespace-normalized snippet against chunks from the same `source_uri`. This
makes the dataset reproducible across clean ingestion and re-chunking, where the
previous UUID labels and implicit `chunk_index` values changed on every run.

Resolution rules (see `src/production_rag/evaluation/anchors.py`):

- A snippet must match exactly one current chunk. Zero matches (`missing`) or
  more than one match (`ambiguous`) raise `AnchorResolutionError` that names the
  example and anchor. Labels are never silently dropped and an arbitrary match is
  never chosen.
- Resolution targets the latest document version per document
  (`RetrievalRepository.list_collection_chunks`), so superseded versions cannot
  create spurious ambiguity.

Baselines are versioned by date and configuration; a new baseline is added as a
separate artifact rather than overwriting this file.

## Legacy baseline (non-reproducible)

The metrics below were produced with the original **UUID-based** labels. Those
labels referenced runtime `uuid4` chunk IDs, so they cannot be reproduced from a
clean rebuild; they are preserved here only as a historical record and must not
be compared against results produced from the anchor-based dataset.

Dataset: FastAPI documentation  
Evaluation examples: 24  
Embedding model: BAAI/bge-small-en-v1.5  
Distance: Cosine

Labeling: legacy UUID chunk IDs (non-reproducible)

| K | Precision@K | Recall@K | Hit@K | MRR |
|---:|---:|---:|---:|---:|
| 1 | 0.4167 | 0.3264 | 0.4167 | 0.4167 |
| 3 | 0.1806 | 0.4028 | 0.4583 | 0.4375 |
| 5 | 0.1500 | 0.5417 | 0.6250 | 0.4750 |
| 10 | 0.0833 | 0.6250 | 0.7083 | 0.4889 |
| 20 | 0.0521 | 0.7569 | 0.8333 | 0.4991 |

## Current anchor-based baseline

**Pending.** The anchor-based dataset has not yet been run against a live
PostgreSQL + Qdrant build. A fresh baseline (with its date, corpus revision,
embedding model, and retrieval parameters) must be recorded here after a real
evaluation run; no metrics are listed until then.
