import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationExample:
    id: str
    question: str
    reference_answer: str
    relevant_chunks: frozenset[str]


def load_dataset(path: Path) -> list[EvaluationExample]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Evaluation dataset must contain a JSON array")

    for _ in data:
        if not isinstance(_, dict):
            raise ValueError("Each evaluation example must be a JSON object")

    return [
        EvaluationExample(
            id=raw["id"],
            question=raw["question"],
            reference_answer=raw["reference_answer"],
            relevant_chunks=frozenset(raw["relevant_chunks"]),
        )
        for raw in data
    ]
