"""LLM client via OpenRouter (OpenAI-compatible API)."""
from openai import AsyncOpenAI
from config import OPENROUTER_API_KEY, CLAUDE_MODEL

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
    return _client


async def ask(system: str, user: str, max_tokens: int = 1024) -> str:
    client = get_client()
    response = await client.chat.completions.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content
