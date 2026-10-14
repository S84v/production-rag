from pathlib import Path
from types import SimpleNamespace

import pytest

from production_rag.evaluation import (
    TERMINAL_EVENT_MISSING_CODE,
    TERMINAL_EVENT_MISSING_MESSAGE,
)
from production_rag.evaluation import answer as answer_module
from production_rag.evaluation.answer import (
    AnswerEvaluationResult,
    build_test_cases,
    evaluate_example,
)
from production_rag.services.rag import RAGSource


class FakeRAGService:
    def __init__(self, events):
        self.events = events

    async def generate(self, query, collection_name, limit):
        for event in self.events:
            yield event


def make_example():
    return SimpleNamespace(
        id="fastapi-001",
        question="How do you declare a path parameter in FastAPI?",
        reference_answer="Use curly braces in the path.",
    )


def make_rag_source():
    return RAGSource(
        source="body.md",
        source_uri="filesystem://body.md",
        chunk_id="chunk-123",
        chunk_index=8,
        score=0.91,
        content="Path parameters are declared using curly braces.",
    )


def make_sources_event():
    return SimpleNamespace(type="sources", text=None, sources=[make_rag_source()])


def make_text_event(text):
    return SimpleNamespace(type="text", text=text, sources=None)


def make_complete_event():
    return SimpleNamespace(type="complete", text=None, sources=None)


def make_error_event(code, message):
    return SimpleNamespace(
        type="error",
        text=None,
        sources=None,
        error_code=code,
        error_message=message,
    )


def make_result(
    *,
    example_id="fastapi-001",
    generated_answer="A grounded answer.",
    error_code=None,
    error_message=None,
):
    return AnswerEvaluationResult(
        example_id=example_id,
        question="How do you declare a path parameter in FastAPI?",
        reference_answer="Use curly braces in the path.",
        generated_answer=generated_answer,
        retrieved_sources=(make_rag_source(),),
        error_code=error_code,
        error_message=error_message,
    )


@pytest.mark.asyncio
async def test_evaluate_example_collects_answer_and_sources():
    rag_service = FakeRAGService(
        [
            make_sources_event(),
            make_text_event("Use curly braces "),
            make_text_event("in the path."),
            make_complete_event(),
        ]
    )

    result = await evaluate_example(
        example=make_example(),
        rag_service=rag_service,
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is False
    assert result.error_code is None
    assert result.generated_answer == "Use curly braces in the path."
    assert len(result.retrieved_sources) == 1
    assert result.retrieved_sources[0].chunk_id == "chunk-123"


@pytest.mark.asyncio
async def test_evaluate_example_records_terminal_error():
    rag_service = FakeRAGService(
        [
            make_sources_event(),
            make_text_event("Partial answer"),
            make_error_event(
                "generation_incomplete",
                "The answer was incomplete. Please try again.",
            ),
        ]
    )

    result = await evaluate_example(
        example=make_example(),
        rag_service=rag_service,
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is True
    assert result.error_code == "generation_incomplete"
    assert result.error_message == "The answer was incomplete. Please try again."
    assert result.generated_answer == "Partial answer"
    assert len(result.retrieved_sources) == 1


@pytest.mark.asyncio
async def test_evaluate_example_records_missing_terminal_event():
    rag_service = FakeRAGService(
        [
            make_sources_event(),
            make_text_event("Partial answer"),
        ]
    )

    result = await evaluate_example(
        example=make_example(),
        rag_service=rag_service,
        collection_name="fastapi",
        limit=5,
    )

    assert result.failed is True
    assert result.error_code == TERMINAL_EVENT_MISSING_CODE
    assert result.error_message == TERMINAL_EVENT_MISSING_MESSAGE


def test_build_test_cases_excludes_failed_examples():
    success = make_result(example_id="ok-001", generated_answer="Good answer.")
    failed = make_result(
        example_id="bad-001",
        generated_answer="Partial answer",
        error_code="generation_failed",
        error_message="The answer could not be generated. Please try again.",
    )

    test_cases = build_test_cases([success, failed])

    assert len(test_cases) == 1
    assert test_cases[0].input == success.question
    assert test_cases[0].actual_output == "Good answer."
    assert test_cases[0].retrieval_context == [
        "Path parameters are declared using curly braces."
    ]
    # A failed example must never surface as a scored test case.
    assert all(case.actual_output != "Partial answer" for case in test_cases)


@pytest.mark.asyncio
async def test_main_skips_deepeval_when_no_usable_cases(monkeypatch):
    failed = make_result(
        example_id="bad-001",
        generated_answer="Partial answer",
        error_code="generation_failed",
        error_message="The answer could not be generated. Please try again.",
    )

    monkeypatch.setattr(
        answer_module,
        "parse_args",
        lambda: SimpleNamespace(
            dataset=Path("unused.json"),
            collection="fastapi",
            limit=5,
        ),
    )
    monkeypatch.setattr(answer_module, "load_dataset", lambda path: [])

    async def fake_collect_results(examples, collection_name, limit):
        return [failed]

    monkeypatch.setattr(answer_module, "collect_results", fake_collect_results)

    calls = []
    monkeypatch.setattr(
        answer_module,
        "deepeval_evaluate",
        lambda **kwargs: calls.append(kwargs),
    )

    await answer_module.main()

    assert calls == []
