"""All AI-provider calls live here. Only Google Gemini (google-genai SDK) is implemented.

To add a provider, implement the same three functions and switch on config.AI_PROVIDER.
"""
from __future__ import annotations

from functools import lru_cache

from gt import config

EMBED_DIM = 768


@lru_cache(maxsize=1)
def _client():
    if not config.ai_ready():
        raise RuntimeError("AI provider not configured (set AI_PROVIDER=gemini and GEMINI_API_KEY).")
    from google import genai

    return genai.Client(api_key=config.GEMINI_API_KEY)


def vision_json(image_bytes: bytes, mime_type: str, prompt: str, schema: dict) -> str:
    """Ask the vision model for JSON matching `schema`. Returns the raw text (parsed by the caller)."""
    from google.genai import types

    resp = _client().models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_json_schema=schema, temperature=0.2
        ),
    )
    return resp.text or ""


def embed(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """task: RETRIEVAL_DOCUMENT for stored items, RETRIEVAL_QUERY for search queries."""
    from google.genai import types

    resp = _client().models.embed_content(
        model=config.GEMINI_EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=EMBED_DIM),
    )
    return [list(e.values) for e in resp.embeddings]


def generate_text(prompt: str) -> str:
    from google.genai import types

    resp = _client().models.generate_content(
        model=config.GEMINI_VISION_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return resp.text or ""


def model_name(kind: str = "vision") -> str:
    return f"{config.AI_PROVIDER}:{config.GEMINI_VISION_MODEL if kind == 'vision' else config.GEMINI_EMBED_MODEL}"
