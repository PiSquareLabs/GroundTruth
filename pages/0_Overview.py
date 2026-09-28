"""Overview page."""
import streamlit as st

from gt import db
from gt.ui import page_setup

page_setup("Overview")

st.title("🌱 Ground Truth")
st.markdown(
    "**Field evidence for civic and environmental work, organized by AI and delivered by Cloudinary.** "
    "NGOs and volunteers upload photos of drain cleaning, tree planting, road repair and waste clearing. "
    "Ground Truth groups them by project, place and time, makes them searchable by meaning, "
    "suggests before/after pairs for a person to confirm, and builds a traceable impact report."
)

projects = db.projects()
assets = db.assets()
confirmed = db.pairs("confirmed")
needs_review = sum(1 for a in assets if a.get("needs_review"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Projects", len(projects))
c2.metric("Images", len(assets))
c3.metric("Confirmed before/after pairs", len(confirmed))
c4.metric("Analyses flagged for review", needs_review)

if not assets:
    st.warning("No seed data loaded yet. Run `python scripts/seed_cloudinary.py` after adding images to `seed/images/`.")
else:
    st.subheader("Projects")
    for p in projects:
        st.markdown(f"**{p['name']}** · {p.get('location_name') or 'location not set'} · {p['asset_count']} images  \n"
                    f"{p.get('description') or ''}")

st.divider()
st.markdown(
    "**Where to go next:** 🗂️ *Assets* to browse evidence · 🔎 *Search* by meaning · "
    "🔁 *Pairs* to review before/after suggestions · 📄 *Report* for the impact report · "
    "🧾 *Trace* to follow any image back to its original."
)
st.caption("AI-produced captions, tags and summaries are labelled “AI-suggested”. "
           "Reports describe visible difference between confirmed paired images; they do not verify environmental outcomes.")
