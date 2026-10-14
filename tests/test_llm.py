from types import SimpleNamespace

import pytest

from production_rag.services.llm import GenerationError, LLMService


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
    client = FakeClient([SimpleNamespace(type="response.completed")])
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
            "max_output_tokens": service.max_output_tokens,
            "stream": True,
        }
    ]


@pytest.mark.asyncio
async def test_generate_uses_configured_max_output_tokens(monkeypatch):
    monkeypatch.setattr(
        "production_rag.services.llm.get_settings",
        lambda: SimpleNamespace(
            deepseek_model="test-model",
            max_output_tokens=256,
        ),
    )

    client = FakeClient([SimpleNamespace(type="response.completed")])
    service = LLMService(client=client)

    chunks = [
        chunk
        async for chunk in service.generate(
            prompt="What is FastAPI?",
            instructions="Answer briefly.",
        )
    ]

    assert chunks == []
    assert client.responses.calls[0]["max_output_tokens"] == 256


async def collect_until_error(service: LLMService) -> tuple[list[str], GenerationError]:
    chunks: list[str] = []

    with pytest.raises(GenerationError) as excinfo:
        async for chunk in service.generate(prompt="q", instructions="i"):
            chunks.append(chunk)

    return chunks, excinfo.value


@pytest.mark.asyncio
async def test_generate_raises_on_failed_response():
    secret = "provider-internal-detail: quota exceeded"
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="partial"),
        SimpleNamespace(
            type="response.failed",
            response=SimpleNamespace(
                status="failed",
                error=SimpleNamespace(message=secret),
            ),
        ),
    ]
    service = LLMService(client=FakeClient(events))

    chunks, error = await collect_until_error(service)

    assert chunks == ["partial"]
    assert error.code == "generation_failed"
    assert error.message == "The answer could not be generated. Please try again."
    assert secret not in str(error)
    assert secret not in error.message


@pytest.mark.asyncio
async def test_generate_raises_on_incomplete_response():
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="partial"),
        SimpleNamespace(
            type="response.incomplete",
            response=SimpleNamespace(
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            ),
        ),
    ]
    service = LLMService(client=FakeClient(events))

    chunks, error = await collect_until_error(service)

    assert chunks == ["partial"]
    assert error.code == "generation_incomplete"
    assert error.message == "The answer was incomplete. Please try again."


@pytest.mark.asyncio
async def test_generate_raises_when_stream_ends_without_completion():
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="partial"),
    ]
    service = LLMService(client=FakeClient(events))

    chunks, error = await collect_until_error(service)

    assert chunks == ["partial"]
    assert error.code == "generation_incomplete"
