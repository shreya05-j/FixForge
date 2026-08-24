import os
import instructor
from groq import AsyncGroq
from core.config import settings

def get_async_client():
    """
    Initializes the Async Groq client wrapped with Instructor
    for structured Pydantic schema validation.
    """
    api_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "dummy-key")
    client = AsyncGroq(api_key=api_key)
    # Using JSON mode for robust structured output compatibility
    return instructor.from_groq(client, mode=instructor.Mode.JSON)

async_llm_client = get_async_client()
