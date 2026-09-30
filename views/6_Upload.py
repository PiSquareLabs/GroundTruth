"""Upload photos + live analysis (disabled in demo mode)."""
import io
import re
from datetime import datetime

import streamlit as st

from gt import analysis, config, db, exif, media, pairing, trust
from gt.ui import next_step, page_header, page_setup

page_setup("Upload photos", ":material/add_a_photo:")
page_header("Step 1 of 4 · Collect", "Upload photos",
            "Add field photos to a project. Each one is stored, read for date and location, and described by AI.",
            ["Choose the project the photos belong to, or create a new one.", "Add JPG, PNG or WebP photos.",
             "If a photo has no date or GPS, type it in so it can be matched with other photos.",
             "Click Upload and analyze. New before/after suggestions appear on Review pairs."])

if config.DEMO_MODE:
    st.info("Uploading is turned off in this read-only demo. To try it, run locally with `DEMO_MODE=false`, "
            "`CLOUDINARY_URL` and `GEMINI_API_KEY`. Here is what happens to each photo:", icon=":material/lock:")
    ingest = [("cloud_upload", "Stored in Cloudinary", "The original file is kept untouched."),
              ("pin_drop", "Date and place read", "Read from the photo's EXIF, or entered by you."),
              ("smart_toy", "Described by AI", "A caption, tags and activity type, labelled AI-suggested."),
              ("compare", "Pairs suggested", "Photos of the same spot are matched for you to review.")]
    for col, (icon, title, text) in zip(st.columns(4), ingest):
        with col.container(border=True):
            st.markdown(f":material/{icon}: **{title}**")
            st.caption(text)
    next_step("Explore the evidence", "See every photo and search by meaning.", "Open library", "views/1_Assets.py")
    st.stop()
if not config.live_enabled():
    st.warning("Set `CLOUDINARY_URL` and `GEMINI_API_KEY` to enable uploads.")
    st.stop()

projects = db.projects()
opts = [p["id"] for p in projects] + ["__new__"]
names = {p["id"]: p["name"] for p in projects} | {"__new__": "➕ New project"}
st.subheader("1 · Choose a project")
pid = st.selectbox("Project", opts, format_func=names.get, label_visibility="collapsed")
if pid == "__new__":
    c1, c2 = st.columns(2)
    new_name = c1.text_input("Project name")
    new_loc = c2.text_input("Location (free text)")
    new_desc = st.text_area("Description", height=80)

st.subheader("2 · Add photos")
files = st.file_uploader("Photos (JPEG/PNG/WebP)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

# Capture date and location come from EXIF when present; otherwise the uploader can enter them.
# Pair suggestions need both (location proximity + time ordering), so missing values are asked for here.
entered: dict[str, dict] = {}
if files:
    st.subheader("3 · Fill in what the photo doesn't know")
    for f in files:
        meta = exif.extract(io.BytesIO(f.getvalue()))
        k = f.name
        with st.container(border=True):
            st.markdown(f"**{f.name}**")
            st.caption(("date from photo" if meta["captured_at"] else "no date in photo") + " · "
                       + ("GPS from photo" if meta["lat"] is not None else "no GPS in photo"))
            c1, c2, c3, c4 = st.columns([1.2, 1, 1.1, 1.1])
            dd, dt, dg = bool(meta["captured_at"]), bool(meta["captured_at"]), meta["lat"] is not None
            d = c1.date_input("Date" + (" · from photo" if dd else ""), value=None, key=f"d_{k}", disabled=dd, format="YYYY-MM-DD")
            t = c2.time_input("Time" + (" · from photo" if dt else ""), value=None, key=f"t_{k}", disabled=dt, step=300)
            lat = c3.number_input("Latitude" + (" · from photo" if dg else ""), value=None, min_value=-90.0, max_value=90.0,
                                  format="%.6f", key=f"la_{k}", disabled=dg)
            lng = c4.number_input("Longitude" + (" · from photo" if dg else ""), value=None, min_value=-180.0, max_value=180.0,
                                  format="%.6f", key=f"lo_{k}", disabled=dg)
            entered[k] = {"date": d, "time": t, "lat": lat, "lng": lng}

st.subheader("4 · Upload and analyze")
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
        with st.status(f"{f.name}: Uploading to Cloudinary…", expanded=False) as s:
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
            s.update(label=f"{f.name}: Analyzing with AI…")
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
            s.update(label=f"{f.name}: " + ("Needs review" if an.get("needs_review") else f"Analyzed · {an.get('caption')}"),
                     state="error" if an.get("needs_review") else "complete")
        bar.progress((i + 1) / len(files))

    n = pairing.save_suggestions(pairing.suggest(db.assets()))
    st.success(f"Uploaded {len(files)} image(s). {n} pair suggestion(s) refreshed.")
    st.page_link("views/3_Pairs.py", label="Review pairs →")
else:
    next_step("Explore the evidence", "See every photo and search by meaning.", "Open library", "views/1_Assets.py")
