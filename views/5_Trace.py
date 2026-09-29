"""Traceability panel: follow any image back to its original, metadata, analysis and transformations."""
import streamlit as st

from gt import db, media, trust
from gt.ui import AI_BADGE, demo_banner, page_setup, synthetic_badge

page_setup("Trace", "🧾")
st.title("🧾 Traceability")

assets = db.assets()
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

ids = [a["id"] for a in assets]
labels = {a["id"]: f"{a['id']} · {a.get('project_name') or ''} · {(a.get('captured_at') or 'no date')[:10]}" for a in assets}
qp = st.query_params.get("asset")
sel = st.selectbox("Image", ids, index=ids.index(qp) if qp in ids else 0, format_func=labels.get)
if sel != qp:
    st.query_params["asset"] = sel
a = db.asset(sel)

left, right = st.columns([1, 1.3])
with left:
    st.image(media.url_for(a, "display", blur_faces=bool(a.get("people_present"))), width="stretch")
    for flag in trust.metadata_flags(a):
        st.warning(flag, icon="⚠️")

with right:
    demo_banner([a])
    synthetic_badge(a)
    st.subheader("1 · Original asset")
    orig = media.original_url(a)
    st.markdown(f"- **Cloudinary public_id:** `{a.get('public_id') or 'not uploaded'}`\n"
                f"- **Original URL (untransformed):** {orig if orig and orig.startswith('http') else '`' + str(orig) + '`'}\n"
                f"- **Uploaded:** {a.get('uploaded_at') or 'unknown'}\n"
                f"- **Size:** {a.get('width')}×{a.get('height')} px, {a.get('format') or '?'}, "
                f"{(a.get('bytes') or 0) // 1024} KB\n"
                f"- **Project:** {a.get('project_name')} · **source:** {a.get('source')}")

    st.subheader("2 · Capture metadata")
    gps = "missing" if a.get("lat") is None else f"{a['lat']:.6f}, {a['lng']:.6f}"
    lines = [f"- **Captured:** {a.get('captured_at') or 'missing'}", f"- **GPS:** {gps}",
             f"- **Metadata source:** {a.get('metadata_source') or 'EXIF'}",
             f"- **Image provenance:** {'AI-generated or edited' if a.get('synthetic') else 'photo'}"]
    if a.get("role"):
        lines.append(f"- **Dataset role (maintainer label, not AI output):** {a['role']}")
    st.markdown("\n".join(lines))
    st.caption("Raw EXIF found in the file:")
    st.json(a.get("exif_json") or {}, expanded=False)

    st.subheader("3 · AI analysis")
    st.caption(f"{AI_BADGE} · model `{a.get('model') or 'n/a'}` · analyzed {a.get('analyzed_at') or 'n/a'}")
    if a.get("needs_review"):
        st.error("The model output did not match the expected JSON schema. Raw output stored below; needs human review.")
    st.json({k: a.get(k) for k in ("caption", "activity_type", "tags", "signals", "people_present")}, expanded=True)
    if a.get("raw_output"):
        with st.expander("Raw model output"):
            st.code(a["raw_output"])
    if a.get("embedding"):
        st.caption(f"Embedding: {len(a['embedding'])} dimensions (caption + tags)")

    st.subheader("4 · Transformation chain")
    log = db.transforms(sel)
    if not log:
        st.caption("No derived versions delivered yet.")
    for t in log:
        st.markdown(f"- **{t['purpose']}** · `{t['transformation']}`  \n  {t['url']}")
    pairs = [p for p in db.pairs() if sel in (p["before_id"], p["after_id"])]
    if pairs:
        st.subheader("5 · Used in pairs")
        for p in pairs:
            role = "before" if p["before_id"] == sel else "after"
            st.markdown(f"- Pair #{p['id']} as **{role}** · status **{p['status']}** · score {p['score']:.2f}")
