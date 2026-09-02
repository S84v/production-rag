from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from production_rag.core.settings import get_settings


class LLMService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        settings = get_settings()

        self.client = client or AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout,
        )
        self.model = settings.deepseek_model

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
            stream=True,
        )

        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta

    async def close(self) -> None:
        await self.client.close()
