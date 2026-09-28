"""Shared page setup and small UI helpers."""
from __future__ import annotations

import streamlit as st

from gt import config, db, seed

AI_BADGE = "🤖 AI-suggested"
SYNTHETIC_BADGE = ":orange-badge[🧪 Synthetic demo data]"
SYNTHETIC_NOTE = ("Seed images are **AI-generated synthetic demo data**. Their locations and dates are "
                  "**fictional**, generated for demonstration. Nothing here is evidence of real-world change.")


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
        if db.get_meta("synthetic") == "1":
            st.warning("🧪 **Synthetic demo data.** AI-generated images; locations and dates are fictional.")
        st.caption(f"Data: {status}")


def synthetic_badge(*assets: dict) -> None:
    """Visible badge whenever any of the given assets is synthetic."""
    if any(a and a.get("synthetic") for a in assets):
        st.markdown(SYNTHETIC_BADGE)


def any_synthetic(assets) -> bool:
    return any(a.get("synthetic") for a in assets)


def ai_label(text: str) -> None:
    st.caption(f"{AI_BADGE} · {text}")
