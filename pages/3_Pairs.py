"""Before/after pair suggestions: per-factor breakdown, human confirm/reject, comparison slider."""
import streamlit as st
from streamlit_image_comparison import image_comparison

from gt import config, db, media, pairing, trust
from gt.ui import page_setup, synthetic_badge

page_setup("Pairs", "🔁")
st.title("🔁 Before / after pairs")
w = config.PAIR_WEIGHTS
st.caption(f"Suggestion score = {w['location']}×location proximity + {w['visual']}×visual similarity "
           f"+ {w['time']}×time ordering. Pairs are only *suggested*; a person confirms or rejects each one.")

assets = {a["id"]: a for a in db.assets()}
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

# In demo mode, review decisions stay in this browser session (the shared demo data is read-only).
overrides = st.session_state.setdefault("pair_overrides", {})
if config.DEMO_MODE:
    st.info("Demo mode: confirm/reject works for your session only and does not change the shared demo data.", icon="🔒")
elif st.button("🔄 Recompute suggestions"):
    n = pairing.save_suggestions(pairing.suggest(list(assets.values())))
    st.success(f"{n} suggestion(s) refreshed; existing review decisions kept.")


def status(p: dict) -> str:
    return overrides.get(p["id"], p["status"])


def decide(p: dict, s: str) -> None:
    if config.DEMO_MODE:
        overrides[p["id"]] = s
    else:
        db.set_pair_status(p["id"], s)


dupe_keys = {frozenset((x, y)) for x, y, _ in trust.find_duplicates(list(assets.values()))}
all_pairs = [p for p in db.pairs() if p["before_id"] in assets and p["after_id"] in assets]
groups = {s: [p for p in all_pairs if status(p) == s] for s in ("suggested", "confirmed", "rejected")}
# A segmented control (not st.tabs) so the slider is rendered only when visible and sizes correctly.
view = st.segmented_control("View", list(groups), default="confirmed" if groups["confirmed"] else "suggested",
                            format_func=lambda s: f"{s.title()} ({len(groups[s])})", label_visibility="collapsed") or "suggested"


def breakdown_table(p: dict) -> None:
    bd = p.get("breakdown") or {}
    rows = []
    for k, v in bd.items():
        v = v if isinstance(v, dict) else {"value": v, "weight": config.PAIR_WEIGHTS.get(k, 0), "note": ""}
        rows.append({"factor": k, "value": v["value"], "weight": v["weight"],
                     "contribution": round(v["value"] * v["weight"], 3), "why": v.get("note", "")})
    st.dataframe(rows, hide_index=True, width="stretch")


def pair_header(p: dict) -> None:
    b, a = assets[p["before_id"]], assets[p["after_id"]]
    synthetic_badge(b, a)
    st.markdown(f"**{b.get('project_name')}** · pair #{p['id']} · score **{p['score']:.2f}** · "
                f"{(b.get('captured_at') or '?')[:10]} → {(a.get('captured_at') or '?')[:10]}")
    if frozenset((b["id"], a["id"])) in dupe_keys:
        st.warning("These two images look like near-duplicates; check that 'after' really is a later photo.", icon="⚠️")


if view == "suggested":
    if not groups["suggested"]:
        st.caption("No pending suggestions.")
    for p in groups["suggested"]:
        b, a = assets[p["before_id"]], assets[p["after_id"]]
        with st.container(border=True):
            pair_header(p)
            c1, c2, c3 = st.columns([1, 1, 1.3])
            c1.image(media.url_for(b, "thumb", blur_faces=bool(b.get("people_present"))), caption=f"Before · {b['id']}")
            c2.image(media.url_for(a, "thumb", blur_faces=bool(a.get("people_present"))), caption=f"After · {a['id']}")
            with c3:
                breakdown_table(p)
                x, y = st.columns(2)
                x.button("✅ Confirm", key=f"c{p['id']}", on_click=decide, args=(p, "confirmed"), width="stretch")
                y.button("❌ Reject", key=f"r{p['id']}", on_click=decide, args=(p, "rejected"), width="stretch")

if view == "confirmed":
    if not groups["confirmed"]:
        st.caption("No confirmed pairs yet.")
    for p in groups["confirmed"]:
        b, a = assets[p["before_id"]], assets[p["after_id"]]
        blur = bool(b.get("people_present") or a.get("people_present"))
        with st.container(border=True):
            pair_header(p)
            st.caption("Slider shows the visible difference between confirmed paired images. "
                       "It does not verify an environmental outcome."
                       + (" These are synthetic images: not evidence of real change." if b.get("synthetic") else ""))
            ub, ua = media.url_for(b, "compare", blur), media.url_for(a, "compare", blur)
            try:
                image_comparison(img1=ub, img2=ua, label1="Before", label2="After", width=760, in_memory=True)
            except Exception as e:
                st.error(f"Could not load the comparison images ({type(e).__name__}).")
            with st.expander("Score breakdown and Cloudinary transformations"):
                breakdown_table(p)
                t = media.transformation_for("compare", blur)
                st.markdown(f"Transformation used for both images: `{t}`")
                st.code(f"{ub}\n{ua}", language=None)
            with st.expander("📣 Campaign card (Cloudinary overlays)"):
                d0, d1 = (b.get("captured_at") or "")[:10], (a.get("captured_at") or "")[:10]
                card = media.campaign_card(b, a, headline=b.get("project_name") or "Field work",
                                           footer=("SYNTHETIC DEMO DATA | " if b.get("synthetic") else "")
                                           + f"Before {d0 or '?'} | After {d1 or '?'} | visible difference, confirmed pair",
                                           blur_faces=blur)
                if card:
                    st.image(card[0], width="stretch")
                    st.markdown(f"[Open / share image]({card[0]})")
                    st.code(card[1], language=None)
                else:
                    st.caption("Needs both images on Cloudinary.")
            st.button("↩️ Move back to suggested", key=f"u{p['id']}", on_click=decide, args=(p, "suggested"))

if view == "rejected":
    if not groups["rejected"]:
        st.caption("No rejected pairs.")
    for p in groups["rejected"]:
        with st.container(border=True):
            pair_header(p)
            st.button("↩️ Move back to suggested", key=f"u{p['id']}", on_click=decide, args=(p, "suggested"))
