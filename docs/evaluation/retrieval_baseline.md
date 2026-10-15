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

## Anchor-based baseline (2026-10-16)

This is the current, **reproducible** baseline. It is deliberately separate from
the legacy UUID-based baseline above and must not be compared with it: the labels
here are content anchors, the corpus is the prepared corpus (MkDocs include
directives expanded; see ADR-006 and `docs/corpus.md`), and the corpus revision
and configuration below differ.

Recorded as a new dated artifact, leaving existing results untouched:

```text
data/evaluation/results/fastapi-retrieval-baseline-2026-10-16.json
```

### Configuration

| Setting | Value |
| --- | --- |
| Dataset | `data/evaluation/fastapi.json` (29 examples) |
| Collection | `fastapi` |
| Corpus | FastAPI revision `244d66308d6c525f394d0c2ce32dabceb2ed262b`, 135 prepared documents |
| Current chunks / vectors | 1,100 |
| Embedding model | `BAAI/bge-small-en-v1.5`, version `1` |
| Embedding dimensions | 384 |
| Distance | Cosine |
| Reranker | none |
| Application default retrieval depth | K = 5 |

### Results

| K | Precision@K | Recall@K | Hit@K | MRR |
|---:|---:|---:|---:|---:|
| 5 | 0.1310 | 0.5977 | 0.6552 | 0.5316 |
| 10 | 0.0862 | 0.7241 | 0.8276 | 0.5595 |
| 20 | 0.0500 | 0.8046 | 0.8966 | 0.5650 |

**K = 5 is the application's current default retrieval depth** (the `POST /query`
default `limit` and the evaluation CLI default). **K = 10 and K = 20 are
diagnostic candidate-depth measurements**; the application does not retrieve at
those depths, and they are recorded only to show how recall behaves with deeper
candidate sets.

Recall and hit rate increase with K while precision decreases, which is the
expected shape of a fixed ranking read at greater depth; no reranker or result
filtering was applied. Per-example metrics are not recorded here.
