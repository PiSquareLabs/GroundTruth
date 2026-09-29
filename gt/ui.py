"""Shared page setup and small UI helpers."""
from __future__ import annotations

import streamlit as st

from gt import config, db, seed

AI_BADGE = "🤖 AI-suggested"
AI_IMAGE_BADGE = ":orange-badge[🧪 AI-generated / edited image]"
REAL_PHOTO_BADGE = ":blue-badge[📷 Real photo]"
DEMO_META_BADGE = ":gray-badge[📍 Demo location & date]"


def dataset_note() -> str | None:
    """Seed-level provenance note (seed/dataset.json), shown wherever demo data appears."""
    return db.get_meta("dataset_note") or None


def demo_banner(assets=None) -> None:
    note = dataset_note()
    if note and (assets is None or any(a.get("source") == "seed" for a in assets)):
        st.warning(note, icon="🧪")


@st.cache_resource(show_spinner="Loading evidence database…")
def _boot(seed_mtime: float) -> str:  # re-runs when the seed file changes
    return seed.ensure_loaded()


def page_setup(title: str, icon: str = "🌱") -> None:
    st.set_page_config(page_title=f"{title} · Ground Truth", page_icon=icon, layout="wide")
    status = _boot(config.SEED_FILE.stat().st_mtime if config.SEED_FILE.exists() else 0.0)
    with st.sidebar:
        if config.DEMO_MODE:
            st.info("**Demo mode (read-only).** Browsing a pre-analyzed seed dataset. "
                    "Uploads and live AI analysis are disabled.", icon="🔒")
        elif config.live_enabled():
            st.success("**Live mode.** Uploads and AI analysis enabled.", icon="⚡")
        else:
            st.warning("**Live mode, not configured.** Set CLOUDINARY_URL and GEMINI_API_KEY "
                       "to enable uploads.", icon="⚠️")
        if dataset_note():
            st.caption("🧪 Demo dataset: after images AI-edited; sites & dates illustrative. "
                       "Details on each image's Trace page.")
        st.caption(f"Data: {status}")


def _badges(a: dict) -> str:
    out = [AI_IMAGE_BADGE if a.get("synthetic") else (REAL_PHOTO_BADGE if dataset_note() else "")]
    if "fictional" in (a.get("metadata_source") or ""):
        out.append(DEMO_META_BADGE)
    return " ".join(b for b in out if b)


def synthetic_badge(*assets: dict) -> None:
    """Provenance badges: real photo vs AI-generated/edited, and demo (fictional) location/date."""
    assets = [a for a in assets if a]
    if len(assets) == 2:
        line = f"Before: {_badges(assets[0])} · After: {_badges(assets[1])}"
    else:
        line = " ".join(_badges(a) for a in assets)
    if line.strip(" ·:BeforAt"):
        st.markdown(line)


def ai_label(text: str) -> None:
    st.caption(f"{AI_BADGE} · {text}")
