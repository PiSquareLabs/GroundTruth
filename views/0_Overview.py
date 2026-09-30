"""Home page."""
import streamlit as st

from gt import config, db, media
from gt.ui import dataset_note, open_tour, page_setup

page_setup("Home", ":material/home:")

st.title("Ground Truth")
st.markdown(
    "**Field evidence for civic and environmental work, organized by AI and delivered by Cloudinary.** "
    "Upload photos of repairs and cleanups, confirm which ones show the same spot before and after, "
    "and share a report where every claim links back to its original photo."
)

projects = db.projects()
assets = db.assets()
suggested = db.pairs("suggested")
confirmed = db.pairs("confirmed")
needs_review = sum(1 for a in assets if a.get("needs_review"))

b1, b2, _ = st.columns([1, 1, 2])
if b1.button("Take the 1-minute tour", icon=":material/play_circle:", type="primary", width="stretch"):
    open_tour()
if b2.button("Browse the evidence", width="stretch"):
    st.switch_page("views/1_Assets.py")

if dataset_note():
    st.warning(dataset_note(), icon=":material/science:")

if not assets:
    st.warning("No seed data loaded yet. Add images to `seed/images/`, describe them in `seed/metadata.csv`, "
               "then run `python scripts/seed_cloudinary.py`.")

st.subheader("How it works")
next_primary = "review" if suggested else "share"
steps = [
    ("1 · Collect", "Upload field photos. Date and location are read from each photo.",
     f"{len(assets)} photos collected", "green", "Upload photos" if config.live_enabled() else "See how upload works",
     "views/6_Upload.py", False),
    ("2 · Explore", "AI describes every photo so you can search by meaning.",
     "AI-described, searchable", "gray", "Open library", "views/1_Assets.py", False),
    ("3 · Review", "Confirm or reject suggested before/after pairs of the same spot.",
     f"{len(suggested)} waiting for you" if suggested else "All reviewed",
     "orange" if suggested else "green", "Review pairs", "views/3_Pairs.py", next_primary == "review"),
    ("4 · Share", "Download a report where every claim links to its photo.",
     f"{len(confirmed)} confirmed pairs ready", "green" if confirmed else "gray", "Open report",
     "views/4_Report.py", next_primary == "share"),
]
for col, (title, desc, badge, color, cta, page, primary) in zip(st.columns(4), steps):
    with col.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(desc)
        st.badge(badge, color=color)
        if st.button(cta, key=f"step_{page}", type="primary" if primary else "secondary", width="stretch"):
            st.switch_page(page)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Projects", len(projects), border=True)
m2.metric("Images", len(assets), border=True)
m3.metric("Confirmed before/after pairs", len(confirmed), border=True)
m4.metric("Analyses flagged for review", needs_review, border=True)

if projects:
    st.subheader("Projects")
    by_project: dict[str, list[dict]] = {}
    for a in assets:
        by_project.setdefault(a["project_id"], []).append(a)
    for row in [projects[i:i + 2] for i in range(0, len(projects), 2)]:
        for col, p in zip(st.columns(2), row):
            with col.container(border=True):
                thumbs, text = st.columns([1.3, 3])
                with thumbs:
                    for i, a in enumerate(by_project.get(p["id"], [])[:2]):
                        st.image(media.url_for(a, "thumb", blur_faces=bool(a.get("people_present")), log=False), width=72)
                with text:
                    st.markdown(f"**{p['name']}**")
                    st.caption(f"{p.get('location_name') or 'location not set'} · {p['asset_count']} images")
                    st.markdown(p.get("description") or "")
                if st.button("View photos →", key=f"view_{p['id']}"):
                    st.session_state.lib_projects = [p["id"]]
                    st.switch_page("views/1_Assets.py")

st.divider()
st.caption("AI-produced captions, tags and summaries are labelled “AI-suggested”. "
           "Reports describe visible difference between confirmed paired images; they do not verify environmental outcomes.")
