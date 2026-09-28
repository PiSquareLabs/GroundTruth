"""Image analysis: strict JSON schema, tolerant parsing, embedding of caption + tags."""
from __future__ import annotations

import json
import re

from gt import ai_provider, config, db

ACTIVITIES = ["drain_cleaning", "tree_planting", "road_repair", "waste_clearing", "other"]
SIGNALS = [
    "standing_water", "clogged_drain", "clear_drain", "litter", "waste_pile", "clean_ground",
    "bare_soil", "saplings", "mature_trees", "potholes", "fresh_asphalt", "debris", "workers_present",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string", "description": "One factual sentence describing what is visible."},
        "activity_type": {"type": "string", "enum": ACTIVITIES},
        "signals": {"type": "array", "items": {"type": "string", "enum": SIGNALS}},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "people_present": {"type": "boolean"},
    },
    "required": ["caption", "activity_type", "signals", "tags", "people_present"],
}

PROMPT = (
    "You are cataloguing field photos of civic and environmental work for an NGO evidence library. "
    "Describe only what is visible; do not guess outcomes, dates, places or quantities. "
    "Return JSON with: caption (one factual sentence), activity_type (the work this photo documents), "
    "signals (visible conditions from the allowed list only), tags (up to 10 short lowercase keywords), "
    "people_present (true if any person is visible)."
)


def parse(raw: str) -> tuple[dict, bool]:
    """Parse model output. Returns (analysis, ok). On failure, returns an empty analysis flagged for review."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not an object")
        caption = data["caption"]
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError("empty caption")
        tags = [str(t).strip().lower() for t in data.get("tags") or [] if str(t).strip()]
        signals = [s for s in data.get("signals") or [] if s in SIGNALS]
        activity = data.get("activity_type")
        return {
            "caption": caption.strip(),
            "activity_type": activity if activity in ACTIVITIES else "other",
            "signals": signals,
            "tags": tags[:10],
            "people_present": bool(data.get("people_present", False)),
            "needs_review": False,
        }, True
    except (ValueError, KeyError, TypeError):
        return {
            "caption": None, "activity_type": None, "signals": [], "tags": [],
            "people_present": False, "needs_review": True,
        }, False


def embedding_text(an: dict) -> str:
    parts = [an.get("caption") or "", (an.get("activity_type") or "").replace("_", " ")]
    parts += [s.replace("_", " ") for s in an.get("signals") or []]
    parts += an.get("tags") or []
    return ". ".join(p for p in parts if p)


def analyze(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Run vision + embedding. Never raises on bad JSON: stores raw output and flags needs_review."""
    raw, used = ai_provider.vision_json(image_bytes, mime_type, PROMPT, SCHEMA)
    an, ok = parse(raw)
    an["raw_output"] = raw
    an["model"] = ai_provider.model_name(used) + " + " + ai_provider.model_name(config.GEMINI_EMBED_MODEL)
    an["analyzed_at"] = db.now_iso()
    text = embedding_text(an)
    an["embedding"] = ai_provider.embed([text])[0] if ok and text else None
    return an
