"""Central configuration. Reads env vars (local .env) first, then Streamlit secrets."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def get(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    if val not in (None, ""):
        return val
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:  # no secrets.toml, or not running under Streamlit
        pass
    return default


def _bool(key: str, default: bool) -> bool:
    return str(get(key, str(default))).strip().lower() in ("1", "true", "yes", "on")


# --- mode -------------------------------------------------------------------
DEMO_MODE = _bool("DEMO_MODE", True)

# --- paths ------------------------------------------------------------------
SEED_DIR = Path(get("SEED_DIR", str(ROOT / "seed")))
SEED_FILE = SEED_DIR / "analysis.json"
SEED_IMAGES = SEED_DIR / "images"
DB_PATH = Path(get("DB_PATH", str(ROOT / "data" / "ground_truth.db")))

# --- Cloudinary ---------------------------------------------------------------
CLOUDINARY_URL = get("CLOUDINARY_URL")
CLOUDINARY_FOLDER = get("CLOUDINARY_FOLDER", "ground-truth")

# --- AI provider ----------------------------------------------------------------
AI_PROVIDER = get("AI_PROVIDER", "gemini")
GEMINI_API_KEY = get("GEMINI_API_KEY") or get("GOOGLE_API_KEY")
GEMINI_VISION_MODEL = get("GEMINI_VISION_MODEL", "gemini-3.8-flash")
# tried in order when the primary model is overloaded (429/5xx) or unavailable to the key (404)
GEMINI_FALLBACK_MODELS = [m.strip() for m in get("GEMINI_FALLBACK_MODELS", "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite").split(",") if m.strip()]
GEMINI_EMBED_MODEL = get("GEMINI_EMBED_MODEL", "gemini-embedding-001")

# --- pair scoring (weights must sum to 1) ---------------------------------------
PAIR_WEIGHTS = {
    "location": float(get("PAIR_W_LOCATION", "0.4")),
    "visual": float(get("PAIR_W_VISUAL", "0.4")),
    "time": float(get("PAIR_W_TIME", "0.2")),
}
LOCATION_SCALE_M = float(get("LOCATION_SCALE_M", "150"))  # distance where proximity = 0.5
PAIR_MIN_SCORE = float(get("PAIR_MIN_SCORE", "0.75"))

# --- trust checks -----------------------------------------------------------------
DUPLICATE_HASH_BITS = int(get("DUPLICATE_HASH_BITS", "32"))  # max differing bits of 256 (pixel hash)
DUPLICATE_THRESHOLD = float(get("DUPLICATE_THRESHOLD", "0.97"))  # embedding fallback when no pixel hash


def cloudinary_ready() -> bool:
    return bool(CLOUDINARY_URL and CLOUDINARY_URL.startswith("cloudinary://"))


def ai_ready() -> bool:
    return AI_PROVIDER == "gemini" and bool(GEMINI_API_KEY)


def live_enabled() -> bool:
    """Uploads + live analysis need demo mode off AND both services configured."""
    return (not DEMO_MODE) and cloudinary_ready() and ai_ready()
