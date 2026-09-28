"""Upload + live analysis (disabled in demo mode)."""
import io
import re

import streamlit as st

from gt import analysis, config, db, exif, media, pairing
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
            res = media.upload(data, public_id=stem, project_id=pid)
            db.upsert("assets", {
                "id": aid, "project_id": pid, "filename": f.name, "public_id": res["public_id"],
                "url": res["secure_url"], "local_path": None, "width": res.get("width"), "height": res.get("height"),
                "bytes": res.get("bytes"), "format": res.get("format"), "uploaded_at": res.get("created_at"),
                "captured_at": meta["captured_at"], "lat": meta["lat"], "lng": meta["lng"],
                "exif_json": meta["exif"], "source": "upload",
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
