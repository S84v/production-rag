from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from production_rag.core.settings import get_settings


class GenerationError(Exception):
    """A Responses API stream did not complete successfully.

    Carries a stable machine ``code`` and a client-safe ``message`` that never
    includes provider error details.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


GENERATION_FAILED_CODE = "generation_failed"
GENERATION_INCOMPLETE_CODE = "generation_incomplete"

GENERATION_FAILED_MESSAGE = "The answer could not be generated. Please try again."
GENERATION_INCOMPLETE_MESSAGE = "The answer was incomplete. Please try again."


class LLMService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()

        self.client = client or AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout,
        )
        self.model = settings.deepseek_model
        self.max_output_tokens = settings.max_output_tokens

    async def generate(
        self,
        prompt: str,
        instructions: str | None = None,
    ) -> AsyncIterator[str]:

        stream = await self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=prompt,
            reasoning={"effort": "none"},
            max_output_tokens=self.max_output_tokens,
            stream=True,
        )

        completed = False

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
            elif event.type == "response.failed":
                # Provider error details are intentionally not read.
                raise GenerationError(
                    code=GENERATION_FAILED_CODE,
                    message=GENERATION_FAILED_MESSAGE,
                )
            elif event.type == "response.incomplete":
                raise GenerationError(
                    code=GENERATION_INCOMPLETE_CODE,
                    message=GENERATION_INCOMPLETE_MESSAGE,
                )
            elif event.type == "response.completed":
                completed = True

        if not completed:
            raise GenerationError(
                code=GENERATION_INCOMPLETE_CODE,
                message=GENERATION_INCOMPLETE_MESSAGE,
            )

    async def close(self) -> None:
        await self.client.close()
