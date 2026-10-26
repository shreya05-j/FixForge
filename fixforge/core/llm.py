import os
import instructor
from openai import AsyncOpenAI
from core.config import settings

def get_async_client():
    """
    Initializes the Async OpenAI-compatible client wrapped with Instructor
    for structured Pydantic schema validation.
    """
    api_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
    base_url = settings.OPENAI_BASE_URL or os.environ.get("OPENAI_BASE_URL", "https://api.ai.kodekloud.com/v1")

    if not api_key:
        api_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "dummy-key")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    # Using JSON mode for robust structured output compatibility with claude-haiku-5-5
    return instructor.from_openai(client, mode=instructor.Mode.JSON)

async_llm_client = get_async_client()

