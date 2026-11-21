from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from policylens.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_chat_model() -> ChatGoogleGenerativeAI:
    if not settings.google_api_key or settings.google_api_key.strip() in {
        "your_gemini_api_key_here", "YOUR_API_KEY"
    }:
        raise LLMConfigurationError(
            "Gemini API key is missing. Copy .env.example to .env and set GOOGLE_API_KEY."
        )
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        api_key=settings.google_api_key,
        temperature=0.1,
        max_retries=2,
    )


def invoke_structured(prompt: str, schema: type[T]) -> T:
    """Call Gemini using provider-constrained Pydantic/JSON-schema output."""
    model = get_chat_model().with_structured_output(schema, method="json_schema")
    result = model.invoke(prompt)
    if isinstance(result, schema):
        return result
    return schema.model_validate(result)
