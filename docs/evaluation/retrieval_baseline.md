# Retrieval Evaluation Baseline

Dataset: FastAPI documentation  
Evaluation examples: 24  
Embedding model: BAAI/bge-small-en-v1.5  
Distance: Cosine

| K | Precision@K | Recall@K | Hit@K | MRR |
|---:|---:|---:|---:|---:|
| 1 | 0.4167 | 0.3264 | 0.4167 | 0.4167 |
| 3 | 0.1806 | 0.4028 | 0.4583 | 0.4375 |
| 5 | 0.1500 | 0.5417 | 0.6250 | 0.4750 |
| 10 | 0.0833 | 0.6250 | 0.7083 | 0.4889 |
| 20 | 0.0521 | 0.7569 | 0.8333 | 0.4991 |
