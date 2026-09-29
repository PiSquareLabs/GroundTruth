"""Upload + live analysis (disabled in demo mode)."""
import io
import re
from datetime import datetime

import streamlit as st

from gt import analysis, config, db, exif, media, pairing, trust
from gt.ui import page_setup

page_setup("Upload", "⬆️")
st.title("⬆️ Upload field photos")

if config.DEMO_MODE:
    st.info("Uploads and live AI analysis are **disabled in the public demo** (read-only). "
            "Run locally with `DEMO_MODE=false`, `CLOUDINARY_URL` and `GEMINI_API_KEY` to enable them.", icon="🔒")
    st.stop()
if not config.live_enabled():
    st.warning("Set CLOUDINARY_URL and GEMINI_API_KEY to enable uploads.")
    st.stop()

projects = db.projects()
opts = [p["id"] for p in projects] + ["__new__"]
names = {p["id"]: p["name"] for p in projects} | {"__new__": "➕ New project"}
pid = st.selectbox("Project", opts, format_func=names.get)
if pid == "__new__":
    c1, c2 = st.columns(2)
    new_name = c1.text_input("Project name")
    new_loc = c2.text_input("Location (free text)")
    new_desc = st.text_area("Description", height=80)

files = st.file_uploader("Photos (JPEG/PNG/WebP)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

# Capture date and location come from EXIF when present; otherwise the uploader can enter them.
# Pair suggestions need both (location proximity + time ordering), so missing values are asked for here.
entered: dict[str, dict] = {}
if files:
    st.markdown("**Capture date and location** (read from the photo when available; fill in what's missing)")
    for f in files:
        meta = exif.extract(io.BytesIO(f.getvalue()))
        c0, c1, c2, c3, c4 = st.columns([2, 1.2, 1, 1.1, 1.1])
        c0.caption(f"**{f.name}**  \n" + ("date from photo" if meta["captured_at"] else "no date in photo") + " · "
                   + ("GPS from photo" if meta["lat"] is not None else "no GPS in photo"))
        k = f.name
        d = c1.date_input("Date", value=None, key=f"d_{k}", disabled=bool(meta["captured_at"]), format="YYYY-MM-DD")
        t = c2.time_input("Time", value=None, key=f"t_{k}", disabled=bool(meta["captured_at"]), step=300)
        lat = c3.number_input("Latitude", value=None, min_value=-90.0, max_value=90.0, format="%.6f",
                              key=f"la_{k}", disabled=meta["lat"] is not None)
        lng = c4.number_input("Longitude", value=None, min_value=-180.0, max_value=180.0, format="%.6f",
                              key=f"lo_{k}", disabled=meta["lat"] is not None)
        entered[k] = {"date": d, "time": t, "lat": lat, "lng": lng}

if st.button("Upload and analyze", type="primary", disabled=not files):
    if pid == "__new__":
        if not new_name.strip():
            st.error("Enter a project name.")
            st.stop()
        pid = re.sub(r"[^a-z0-9]+", "-", new_name.lower()).strip("-")
        db.upsert("projects", {"id": pid, "name": new_name.strip(), "description": new_desc, "location_name": new_loc})

    bar = st.progress(0.0)
    for i, f in enumerate(files):
        data = f.getvalue()
        stem = re.sub(r"[^a-z0-9]+", "-", f.name.rsplit(".", 1)[0].lower()).strip("-")
        aid = f"{pid}-{stem}"
        with st.status(f"{f.name}", expanded=False) as s:
            meta = exif.extract(io.BytesIO(data))
            e = entered.get(f.name, {})
            sources = ["EXIF"] if (meta["captured_at"] or meta["lat"] is not None) else []
            if not meta["captured_at"] and e.get("date"):
                t = e.get("time") or datetime.min.time()
                meta["captured_at"] = datetime.combine(e["date"], t).isoformat()
                sources.append("date entered by uploader")
            if meta["lat"] is None and e.get("lat") is not None and e.get("lng") is not None:
                meta["lat"], meta["lng"] = e["lat"], e["lng"]
                sources.append("location entered by uploader")
            res = media.upload(data, public_id=stem, project_id=pid)
            db.upsert("assets", {
                "id": aid, "project_id": pid, "filename": f.name, "public_id": res["public_id"],
                "url": res["secure_url"], "local_path": None, "width": res.get("width"), "height": res.get("height"),
                "bytes": res.get("bytes"), "format": res.get("format"), "uploaded_at": res.get("created_at"),
                "captured_at": meta["captured_at"], "lat": meta["lat"], "lng": meta["lng"],
                "exif_json": meta["exif"], "source": "upload", "dhash": trust.dhash(io.BytesIO(data)),
                "metadata_source": ", ".join(sources) or "none",
            })
            try:
                an = analysis.analyze(data, f.type or "image/jpeg")
            except Exception as e:
                an = {"needs_review": True, "raw_output": f"ERROR: {e}", "tags": [], "signals": []}
            db.upsert("analyses", {
                "asset_id": aid, "caption": an.get("caption"), "activity_type": an.get("activity_type"),
                "tags": an.get("tags") or [], "signals": an.get("signals") or [],
                "people_present": int(bool(an.get("people_present"))), "embedding": an.get("embedding"),
                "model": an.get("model"), "raw_output": an.get("raw_output"),
                "needs_review": int(bool(an.get("needs_review"))), "analyzed_at": an.get("analyzed_at"),
            }, conflict="asset_id")
            s.update(label=f"{f.name}: {an.get('caption') or 'needs review'}",
                     state="error" if an.get("needs_review") else "complete")
        bar.progress((i + 1) / len(files))

    n = pairing.save_suggestions(pairing.suggest(db.assets()))
    st.success(f"Uploaded {len(files)} image(s). {n} pair suggestion(s) refreshed. Review them on the Pairs page.")
