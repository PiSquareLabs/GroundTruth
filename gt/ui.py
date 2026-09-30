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


def boot() -> str:
    return _boot(config.SEED_FILE.stat().st_mtime if config.SEED_FILE.exists() else 0.0)


TOUR = [
    ("add_a_photo", "Collect", "Volunteers and NGOs upload photos of civic work, like a broken gutter or loose wiring. "
                              "Each photo keeps its date and location."),
    ("photo_library", "Explore", "AI describes every photo, so you can search by typing what you want to see. "
                                 "AI output is always labelled."),
    ("compare", "Review", "Ground Truth suggests photos of the same spot taken before and after the work. "
                          "A person confirms or rejects each pair."),
    ("description", "Share", "Confirmed pairs become a report you can download. Every claim links back to its "
                             "original photo, so anyone can check it."),
]


@st.dialog("How Ground Truth works")
def tour_dialog() -> None:
    i = st.session_state.setdefault("tour_step", 0)
    icon, title, text = TOUR[i]
    st.caption(f"Step {i + 1} of {len(TOUR)}")
    st.progress((i + 1) / len(TOUR))
    st.subheader(f":material/{icon}: {title}")
    st.markdown(text)
    back, nxt = st.columns(2)
    if back.button("Back", disabled=i == 0, width="stretch"):
        st.session_state.tour_step = i - 1
        st.rerun(scope="fragment")
    if i < len(TOUR) - 1:
        if nxt.button("Next", type="primary", width="stretch"):
            st.session_state.tour_step = i + 1
            st.rerun(scope="fragment")
    elif nxt.button("Start exploring", type="primary", width="stretch"):
        st.session_state.tour_step = 0
        st.switch_page("views/1_Assets.py")


def open_tour() -> None:
    st.session_state.tour_step = 0
    tour_dialog()


def page_header(step: str, title: str, desc: str, help_steps: list[str]) -> None:
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    with left:
        st.caption(f":green[**{step}**]")
        st.title(title)
        st.markdown(desc)
    with right:
        with st.popover("How this page works", icon=":material/help:"):
            st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(help_steps, 1)))


def next_step(title: str, desc: str, cta: str, page: str) -> None:
    st.divider()
    left, right = st.columns([4, 1], vertical_alignment="center")
    left.caption("Next step")
    left.markdown(f"**{title}**  \n{desc}")
    right.page_link(page, label=cta, icon=":material/arrow_forward:")


def strength(score: float) -> str:
    return "strong" if score >= 0.9 else "good" if score >= 0.75 else "weak"


def provenance_badge(a: dict) -> str:
    """Short badge markup: Real photo vs AI-edited (empty when there is no dataset note)."""
    if a.get("synthetic"):
        return ":orange-badge[AI-edited]"
    return ":blue-badge[Real photo]" if dataset_note() else ""


def page_setup(title: str, icon: str = "🌱") -> None:
    st.set_page_config(page_title=f"{title} · Ground Truth", page_icon=icon, layout="wide")
    status = boot()
    with st.sidebar:
        if st.button("How Ground Truth works", icon=":material/school:", type="tertiary"):
            open_tour()
        st.divider()
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
