from types import SimpleNamespace

import pytest

from production_rag.services.llm import LLMService


class FakeResponses:
    def __init__(self, events):
        self.events = events
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        async def stream():
            for event in self.events:
                yield event

        return stream()


class FakeClient:
    def __init__(self, events):
        self.responses = FakeResponses(events)


@pytest.mark.asyncio
async def test_generate_yields_streamed_text():
    events = [
        SimpleNamespace(
            type="response.output_text.delta",
            delta="FastAPI",
        ),
        SimpleNamespace(
            type="response.output_text.delta",
            delta=" is a",
        ),
        SimpleNamespace(
            type="response.output_text.delta",
            delta=" Python framework.",
        ),
        SimpleNamespace(
            type="response.completed",
        ),
    ]

    client = FakeClient(events)
    service = LLMService(client=client)

    chunks = [
        chunk
        async for chunk in service.generate(
            prompt="What is FastAPI?",
            instructions="Answer briefly.",
        )
    ]

    assert chunks == [
        "FastAPI",
        " is a",
        " Python framework.",
    ]


@pytest.mark.asyncio
async def test_generate_configures_streaming_and_disables_reasoning():
    client = FakeClient([])
    service = LLMService(client=client)

    chunks = [
        chunk
        async for chunk in service.generate(
            prompt="What is FastAPI?",
            instructions="Answer briefly.",
        )
    ]

    assert chunks == []

    assert client.responses.calls == [
        {
            "model": service.model,
            "instructions": "Answer briefly.",
            "input": "What is FastAPI?",
            "reasoning": {"effort": "none"},
            "stream": True,
        }
    ]
