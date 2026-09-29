"""Projects and asset grid with filters."""
from datetime import date

import streamlit as st

from gt import db, media, trust
from gt.ui import AI_BADGE, SYNTHETIC_NOTE, any_synthetic, page_setup, synthetic_badge

page_setup("Assets", "🗂️")
st.title("🗂️ Evidence library")

assets = db.assets()
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

if any_synthetic(assets):
    st.warning(SYNTHETIC_NOTE, icon="🧪")

projects = {p["id"]: p["name"] for p in db.projects()}
activities = sorted({a["activity_type"] for a in assets if a.get("activity_type")})
dates = [date.fromisoformat(a["captured_at"][:10]) for a in assets if a.get("captured_at")]

f1, f2, f3 = st.columns([1, 1, 1.2])
sel_projects = f1.multiselect("Project", list(projects), format_func=projects.get)
sel_acts = f2.multiselect("Activity (AI-suggested)", activities)
date_range = f3.date_input("Captured between", value=(min(dates), max(dates))) if dates else None
o1, o2, o3 = st.columns(3)
include_undated = o1.checkbox("Include images without a capture date", value=True)
only_flagged = o2.checkbox("Only images with flags")
blur = o3.checkbox("Blur faces where people may appear", value=True,
                   help="Uses Cloudinary's e_blur_faces transformation on delivery; the original is not modified.")


def keep(a: dict) -> bool:
    if sel_projects and a["project_id"] not in sel_projects:
        return False
    if sel_acts and a.get("activity_type") not in sel_acts:
        return False
    if a.get("captured_at"):
        if isinstance(date_range, tuple) and len(date_range) == 2:
            d = date.fromisoformat(a["captured_at"][:10])
            if not (date_range[0] <= d <= date_range[1]):
                return False
    elif not include_undated:
        return False
    if only_flagged and not trust.metadata_flags(a):
        return False
    return True


shown = [a for a in assets if keep(a)]
st.caption(f"Showing {len(shown)} of {len(assets)} images")

dupes = trust.find_duplicates(assets)
if dupes:
    with st.expander(f"⚠️ {len(dupes)} possible near-duplicate pair(s)"):
        for x, y, s, how in dupes:
            st.write(f"`{x}` ↔ `{y}` — {how} similarity {s:.3f}")

for pid in [p for p in projects if any(a["project_id"] == p for a in shown)]:
    group = [a for a in shown if a["project_id"] == pid]
    st.subheader(f"{projects[pid]} · {len(group)}")
    cols = st.columns(4)
    for i, a in enumerate(group):
        with cols[i % 4]:
            with st.container(border=True):
                st.image(media.url_for(a, "thumb", blur_faces=blur and bool(a.get("people_present"))), width="stretch")
                synthetic_badge(a)
                st.markdown(f"**{(a.get('activity_type') or 'unclassified').replace('_', ' ')}** · "
                            f"{(a.get('captured_at') or 'no date')[:10]}")
                if a.get("caption"):
                    st.caption(f"{AI_BADGE}: {a['caption']}")
                if a.get("signals"):
                    st.caption("Signals: " + ", ".join(a["signals"]))
                for flag in trust.metadata_flags(a):
                    st.caption(f"⚠️ {flag}")
                st.page_link("views/5_Trace.py", label="Trace", icon="🧾", query_params={"asset": a["id"]})
