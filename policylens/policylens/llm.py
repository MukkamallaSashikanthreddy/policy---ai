from __future__ import annotations

import logging
import random
import time
from functools import lru_cache
from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from policylens.config import settings

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# A small, bounded retry budget for temporary Gemini capacity/server errors.
# This is deliberately not used for authentication, invalid-request, or other 4xx errors.
_RETRY_DELAYS_SECONDS = (1.0,)


class LLMConfigurationError(RuntimeError):
    pass


class GeminiTemporarilyUnavailable(RuntimeError):
    """Raised when Gemini remains unavailable after bounded retries."""


def _is_retryable_server_error(exc: Exception) -> bool:
    """Recognize transient Gemini 5xx/UNAVAILABLE errors without retrying 4xx."""
    parts = [f"{type(exc).__name__}: {exc}"]
    current = exc.__cause__ or exc.__context__
    depth = 0
    while current is not None and depth < 4:
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
        depth += 1

    message = " ".join(parts).upper()
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if value is not None:
            message += f" {value}".upper()

    return any(token in message for token in (
        "503", "UNAVAILABLE", "502", "BAD GATEWAY", "504", "GATEWAY TIMEOUT",
        "500", "INTERNAL SERVER ERROR",
    ))


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
        max_output_tokens=900,
        # Keep SDK-level retries modest; invoke_structured adds a bounded outer retry
        # specifically for transient server-capacity errors.
        max_retries=0,
    )


@lru_cache(maxsize=16)
def _structured_model(schema: type[BaseModel]):
    """Build each schema-bound Gemini runnable once per process."""
    return get_chat_model().with_structured_output(schema, method="json_schema")


def invoke_structured(prompt: str, schema: type[T]) -> T:
    """Call Gemini with structured output and one short retry for transient 5xx errors."""
    model = _structured_model(schema)

    for attempt in range(len(_RETRY_DELAYS_SECONDS) + 1):
        try:
            result = model.invoke(prompt)
            if isinstance(result, schema):
                return result
            return schema.model_validate(result)
        except Exception as exc:
            if not _is_retryable_server_error(exc):
                raise

            if attempt >= len(_RETRY_DELAYS_SECONDS):
                raise GeminiTemporarilyUnavailable(
                    "Gemini is temporarily overloaded (503 UNAVAILABLE). "
                    "PolicyLens completed local retrieval, and your uploaded PDF/index are preserved. "
                    "Please wait 30–60 seconds and submit the question again. "
                    "This is a temporary provider-capacity issue, not a PDF or ChromaDB failure."
                ) from exc

            delay = _RETRY_DELAYS_SECONDS[attempt] + random.uniform(0.0, 0.35)
            logger.warning(
                "Gemini returned a temporary server/capacity error; retry %s/%s in %.2f seconds",
                attempt + 1,
                len(_RETRY_DELAYS_SECONDS),
                delay,
            )
            time.sleep(delay)

    # Defensive fallback; the loop always returns or raises.
    raise RuntimeError("Gemini request ended unexpectedly.")
