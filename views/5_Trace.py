"""Trace an image back to its original, metadata, AI analysis and transformations."""
import streamlit as st

from gt import db, media, trust
from gt.ui import AI_BADGE, demo_banner, next_step, page_header, page_setup, synthetic_badge

page_setup("Trace an image", ":material/account_tree:")
page_header("Check", "Trace an image",
            "Follow any photo back to its original file, capture details, AI output and every edit applied.",
            ["Pick an image from the list, or arrive here from a Trace button.",
             "Use the tabs to see each stage of the image’s history.",
             "Use this to check where any number or claim in the report came from."])

assets = db.assets()
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

ids = [a["id"] for a in assets]
labels = {a["id"]: f"{a['id']} · {a.get('project_name') or ''} · {(a.get('captured_at') or 'no date')[:10]}" for a in assets}
qp = st.query_params.get("asset")
sel = st.selectbox("Image to trace", ids, index=ids.index(qp) if qp in ids else 0, format_func=labels.get)
if sel != qp:
    st.query_params["asset"] = sel
a = db.asset(sel)


def table(rows: list[tuple[str, str]]) -> None:
    st.dataframe([{"": k, " ": v} for k, v in rows], hide_index=True, width="stretch", row_height=38)


left, right = st.columns([5, 7])
with left:
    st.image(media.url_for(a, "display", blur_faces=bool(a.get("people_present"))), width="stretch")
    demo_banner([a])
    synthetic_badge(a)
    for flag in trust.metadata_flags(a):
        st.warning(flag, icon=":material/warning:")

with right:
    t1, t2, t3, t4, t5 = st.tabs(["1 · Original", "2 · Capture", "3 · AI analysis", "4 · Transformations", "5 · Used in pairs"])

    with t1:
        st.caption("The untouched file as stored in Cloudinary.")
        orig = media.original_url(a)
        table([("Public ID", a.get("public_id") or "not uploaded"), ("Original URL", str(orig)),
               ("Uploaded", a.get("uploaded_at") or "unknown"),
               ("Size", f"{a.get('width')}×{a.get('height')} px, {(a.get('bytes') or 0) // 1024} KB"),
               ("Format", a.get("format") or "?"), ("Project", a.get("project_name") or ""),
               ("Source", a.get("source") or "")])

    with t2:
        st.caption("When and where the photo was taken, and where that information came from.")
        gps = "missing" if a.get("lat") is None else f"{a['lat']:.6f}, {a['lng']:.6f}"
        rows = [("Captured", a.get("captured_at") or "missing"), ("GPS", gps),
                ("Metadata source", a.get("metadata_source") or "EXIF"),
                ("Provenance", "AI-generated or edited" if a.get("synthetic") else "photo")]
        if a.get("role"):
            rows.append(("Dataset role", f"{a['role']} (maintainer label, not AI output)"))
        table(rows)
        with st.expander("Raw EXIF"):
            st.json(a.get("exif_json") or {}, expanded=False)

    with t3:
        st.caption("What the AI model said about this photo. Treat it as a suggestion.")
        st.markdown(f":violet-badge[{AI_BADGE}]")
        if a.get("needs_review"):
            st.error("The model output did not match the expected JSON schema. Raw output stored below; needs human review.")
        table([("Model", f"{a.get('model') or 'n/a'} · analyzed {a.get('analyzed_at') or 'n/a'}"),
               ("Caption", a.get("caption") or "—"), ("Activity", a.get("activity_type") or "—"),
               ("Tags", ", ".join(a.get("tags") or []) or "—"), ("Signals", ", ".join(a.get("signals") or []) or "—"),
               ("People present", "Yes" if a.get("people_present") else "No"),
               ("Embedding", f"{len(a['embedding'])} dimensions (caption + tags)" if a.get("embedding") else "none")])
        with st.expander("Raw model output"):
            st.json({k: a.get(k) for k in ("caption", "activity_type", "tags", "signals", "people_present")}, expanded=True)
            if a.get("raw_output"):
                st.code(a["raw_output"])

    with t4:
        st.caption("Every derived version shown in the app, and the Cloudinary transformation behind it.")
        log = db.transforms(sel)
        if not log:
            st.info("No derived versions delivered yet.")
        else:
            st.dataframe([{"Purpose": t["purpose"], "Transformation": t["transformation"], "URL": t["url"]} for t in log],
                         hide_index=True, width="stretch", column_config={"URL": st.column_config.LinkColumn("URL")})

    with t5:
        st.caption("Pairs this photo belongs to.")
        pairs = [p for p in db.pairs() if sel in (p["before_id"], p["after_id"])]
        if not pairs:
            st.info("This photo is not part of any suggested pair.")
        table([(f"Pair #{p['id']}", f"{'Before' if p['before_id'] == sel else 'After'} · {p['status']} · "
                                    f"score {p['score']:.2f}") for p in pairs]) if pairs else None

next_step("Back to the evidence", "Browse or search other photos.", "Open library", "views/1_Assets.py")
