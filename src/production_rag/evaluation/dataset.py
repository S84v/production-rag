import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationExample:
    id: str
    question: str
    reference_answer: str
    relevant_sources: frozenset[str]


def load_dataset(path: Path) -> list[EvaluationExample]:
    with path.open(encoding="utf-8") as file:
        raw_examples = json.load(file)

    if not isinstance(raw_examples, list):
        raise ValueError("Evaluation dataset must contain a JSON array")

    examples: list[EvaluationExample] = []

    for raw in raw_examples:
        if not isinstance(raw, dict):
            raise ValueError("Each evaluation example must be a JSON object")

        examples.append(
            EvaluationExample(
                id=raw["id"],
                question=raw["question"],
                reference_answer=raw["reference_answer"],
                relevant_sources=frozenset(raw["relevant_sources"]),
            )
        )

    return examples
