"""All AI-provider calls live here. Only Google Gemini (google-genai SDK) is implemented.

To add a provider, implement the same three functions and switch on config.AI_PROVIDER.
"""
from __future__ import annotations

import time
from functools import lru_cache

from gt import config

EMBED_DIM = 768
RETRYABLE = (429, 500, 503)


@lru_cache(maxsize=1)
def _client():
    if not config.ai_ready():
        raise RuntimeError("AI provider not configured (set AI_PROVIDER=gemini and GEMINI_API_KEY).")
    from google import genai

    return genai.Client(api_key=config.GEMINI_API_KEY)


def _generate(contents, gen_config) -> tuple[str, str]:
    """generate_content with retries on overload, then fallback models. Returns (text, model_used)."""
    from google.genai import errors

    models = [config.GEMINI_VISION_MODEL] + [m for m in config.GEMINI_FALLBACK_MODELS if m != config.GEMINI_VISION_MODEL]
    last = None
    for model in models:
        for attempt in range(2):
            try:
                resp = _client().models.generate_content(model=model, contents=contents, config=gen_config)
                return resp.text or "", model
            except errors.APIError as e:
                last = e
                if e.code == 404:  # model not available to this key: try the next one
                    break
                if e.code not in RETRYABLE:
                    raise
                time.sleep(2 * (attempt + 1))
    raise last


def vision_json(image_bytes: bytes, mime_type: str, prompt: str, schema: dict) -> tuple[str, str]:
    """Ask the vision model for JSON matching `schema`. Returns (raw text, model used); caller parses."""
    from google.genai import types

    return _generate(
        [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
        types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema, temperature=0.2),
    )


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """task: RETRIEVAL_DOCUMENT for stored items, RETRIEVAL_QUERY for search queries."""
    from google.genai import types

    resp = _client().models.embed_content(
        model=config.GEMINI_EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=EMBED_DIM),
    )
    return [list(e.values) for e in resp.embeddings]


def generate_text(prompt: str) -> tuple[str, str]:
    """Returns (text, model used)."""
    from google.genai import types

    return _generate(prompt, types.GenerateContentConfig(temperature=0.2))


def model_name(model: str) -> str:
    return f"{config.AI_PROVIDER}:{model}"
