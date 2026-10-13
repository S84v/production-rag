import json
from pathlib import Path

import pytest

from production_rag.evaluation.dataset import ChunkAnchor, load_dataset

DATASET_PATH = Path("data/evaluation/fastapi.json")


def write_dataset(tmp_path: Path, examples: list) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(examples), encoding="utf-8")
    return path


def make_example(relevant_chunks: list) -> dict:
    return {
        "id": "fastapi-001",
        "question": "question",
        "reference_answer": "answer",
        "relevant_chunks": relevant_chunks,
    }


def test_load_dataset_parses_content_anchors(tmp_path: Path) -> None:
    path = write_dataset(
        tmp_path,
        [
            make_example(
                [
                    {
                        "source_uri": "filesystem://path-params.md",
                        "snippet": "You can declare path parameters.",
                    }
                ]
            )
        ],
    )

    examples = load_dataset(path)

    assert len(examples) == 1
    assert examples[0].relevant_chunks == frozenset(
        {
            ChunkAnchor(
                source_uri="filesystem://path-params.md",
                snippet="You can declare path parameters.",
            )
        }
    )


def test_load_dataset_rejects_legacy_string_labels(tmp_path: Path) -> None:
    path = write_dataset(
        tmp_path, [make_example(["e1c41b91-ebc6-43dd-8399-d9377391fa0e"])]
    )

    with pytest.raises(ValueError) as excinfo:
        load_dataset(path)

    message = str(excinfo.value)
    assert "fastapi-001" in message
    assert "legacy" in message.lower()
    assert "source_uri" in message


def test_load_dataset_rejects_non_object_anchor(tmp_path: Path) -> None:
    path = write_dataset(tmp_path, [make_example([42])])

    with pytest.raises(ValueError) as excinfo:
        load_dataset(path)

    assert "invalid chunk anchor" in str(excinfo.value)


def test_load_dataset_rejects_missing_source_uri(tmp_path: Path) -> None:
    path = write_dataset(tmp_path, [make_example([{"snippet": "text"}])])

    with pytest.raises(ValueError) as excinfo:
        load_dataset(path)

    assert "source_uri" in str(excinfo.value)


def test_load_dataset_rejects_empty_snippet(tmp_path: Path) -> None:
    path = write_dataset(
        tmp_path,
        [make_example([{"source_uri": "filesystem://a.md", "snippet": "   "}])],
    )

    with pytest.raises(ValueError) as excinfo:
        load_dataset(path)

    assert "snippet" in str(excinfo.value)


def test_load_dataset_requires_json_array(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({"id": "fastapi-001"}), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON array"):
        load_dataset(path)


def test_repository_dataset_uses_content_anchors() -> None:
    examples = load_dataset(DATASET_PATH)

    assert len(examples) == 24

    for example in examples:
        assert example.relevant_chunks
        for anchor in example.relevant_chunks:
            assert anchor.source_uri.startswith("filesystem://")
            assert anchor.snippet.strip()
