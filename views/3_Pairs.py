"""Review pairs: confirm or reject suggested before/after pairs, one at a time."""
import streamlit as st
from streamlit_image_comparison import image_comparison

from gt import config, db, media, pairing, trust
from gt.ui import AI_BADGE, next_step, page_header, page_setup, provenance_badge, strength

page_setup("Review pairs", ":material/compare:")
page_header("Step 3 of 4 · Review", "Review pairs",
            "Ground Truth suggests photos that may show the same spot before and after the work. You decide.",
            ["Look at the before and after photo.",
             "Confirm if they show the same place before and after the work. Reject if not.",
             "Every decision can be undone. Only confirmed pairs appear in the report."])

assets = {a["id"]: a for a in db.assets()}
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

# In demo mode, review decisions stay in this browser session (the shared demo data is read-only).
overrides = st.session_state.setdefault("pair_overrides", {})


def status(p: dict) -> str:
    return overrides.get(p["id"], p["status"])


def decide(p: dict, s: str, toast: str) -> None:
    if config.DEMO_MODE:
        overrides[p["id"]] = s
    else:
        db.set_pair_status(p["id"], s)
    st.toast(toast)


def skip(n: int) -> None:
    st.session_state.review_idx = (st.session_state.get("review_idx", 0) + 1) % n


dupe_keys = {frozenset((x, y)) for x, y, *_ in trust.find_duplicates(list(assets.values()))}
all_pairs = [p for p in db.pairs() if p["before_id"] in assets and p["after_id"] in assets]
groups = {s: [p for p in all_pairs if status(p) == s] for s in ("suggested", "confirmed", "rejected")}
LABELS = {"suggested": "To review", "confirmed": "Confirmed", "rejected": "Rejected"}
if st.session_state.get("pairs_view") not in groups:
    st.session_state.pairs_view = "suggested" if groups["suggested"] else "confirmed" if groups["confirmed"] else "suggested"

ctl, note = st.columns([3, 2], vertical_alignment="center")
# A segmented control (not st.tabs) so the slider is rendered only when visible and sizes correctly.
view = ctl.segmented_control("View", list(groups), key="pairs_view", required=True,
                             format_func=lambda s: f"{LABELS[s]} ({len(groups[s])})", label_visibility="collapsed")
if config.DEMO_MODE:
    note.caption("Demo: decisions last for this session only.")
elif note.button("Recompute suggestions", icon=":material/refresh:"):
    n = pairing.save_suggestions(pairing.suggest(list(assets.values())))
    st.success(f"{n} suggestion(s) refreshed; existing review decisions kept.")
    st.rerun()

w = config.PAIR_WEIGHTS


def breakdown_table(p: dict) -> None:
    rows = []
    for k, v in (p.get("breakdown") or {}).items():
        v = v if isinstance(v, dict) else {"value": v, "weight": w.get(k, 0), "note": ""}
        rows.append({"Factor": k, "Value": v["value"], "Weight": v["weight"],
                     "Adds": round(v["value"] * v["weight"], 3), "Why": v.get("note", "")})
    st.dataframe(rows, hide_index=True, width="stretch")


def dates(p: dict) -> str:
    b, a = assets[p["before_id"]], assets[p["after_id"]]
    return f"{(b.get('captured_at') or '?')[:10]} → {(a.get('captured_at') or '?')[:10]}"


def photo(a: dict, label: str, blur: bool) -> None:
    st.image(media.url_for(a, "thumb", blur_faces=blur and bool(a.get("people_present"))), width="stretch")
    st.markdown(f"**{label}** · {(a.get('captured_at') or 'no date')[:10]} {provenance_badge(a)}")
    if a.get("caption"):
        st.caption(f"{AI_BADGE}: {a['caption']}")


if view == "suggested":
    todo = groups["suggested"]
    if not todo:
        with st.container(border=True):
            st.subheader("All caught up")
            st.markdown(f"Every suggested pair has been reviewed. {len(groups['confirmed'])} confirmed pairs are "
                        "ready for the report.")
            c1, c2, _ = st.columns([1, 1, 2])
            if c1.button("Build the report", type="primary", width="stretch"):
                st.switch_page("views/4_Report.py")
            if c2.button("See confirmed pairs", width="stretch"):
                st.session_state.pairs_view = "confirmed"
                st.rerun()
    else:
        i = min(st.session_state.get("review_idx", 0), len(todo) - 1)
        st.session_state.review_idx = i
        p = todo[i]
        b, a = assets[p["before_id"]], assets[p["after_id"]]
        with st.container(border=True):
            head, badge = st.columns([3, 2], vertical_alignment="center")
            head.caption(f"Pair {i + 1} of {len(todo)}")
            head.markdown(f"**{b.get('project_name')}** · {dates(p)}")
            badge.badge(f"Match score {p['score']:.2f} · {strength(p['score'])}",
                        color={"strong": "green", "good": "blue", "weak": "orange"}[strength(p["score"])])
            if frozenset((b["id"], a["id"])) in dupe_keys:
                st.warning("These two images look like near-duplicates; check that 'after' really is a later photo.",
                           icon=":material/warning:")
            blur = st.session_state.get("blur_faces", True)
            c1, c2 = st.columns(2)
            with c1:
                photo(b, "Before", blur)
            with c2:
                photo(a, "After", blur)
            st.markdown("**Do these photos show the same spot, before and after the work?**")
            y, n_, s_, _ = st.columns([1.2, 1, 1, 1.5])
            y.button("Yes, confirm pair", key=f"c{p['id']}", type="primary", icon=":material/check:", width="stretch",
                     on_click=decide, args=(p, "confirmed", "Pair confirmed. It will appear in the report."))
            n_.button("No, reject", key=f"r{p['id']}", icon=":material/close:", width="stretch",
                      on_click=decide, args=(p, "rejected", "Pair rejected."))
            if len(todo) > 1:
                s_.button("Skip for now", key=f"s{p['id']}", type="tertiary", on_click=skip, args=(len(todo),))
            st.caption("You can undo either choice later. Only confirmed pairs appear in the report.")
            with st.expander("Why was this pair suggested?"):
                st.caption(f"Suggestion score = {w['location']}×location proximity + {w['visual']}×visual similarity "
                           f"+ {w['time']}×time ordering. Pairs are only *suggested*; a person confirms or rejects each one.")
                breakdown_table(p)

if view == "confirmed":
    if not groups["confirmed"]:
        st.info("No confirmed pairs yet. Confirm a pair on the “To review” view and it will show up here.")
    for row in [groups["confirmed"][i:i + 2] for i in range(0, len(groups["confirmed"]), 2)]:
        for col, p in zip(st.columns(2), row):
            b, a = assets[p["before_id"]], assets[p["after_id"]]
            blur = bool(b.get("people_present") or a.get("people_present"))
            with col.container(border=True):
                st.markdown(f"**{b.get('project_name')}** · pair #{p['id']} · score **{p['score']:.2f}** · {dates(p)}")
                ub, ua = media.url_for(b, "compare", blur), media.url_for(a, "compare", blur)
                try:
                    image_comparison(img1=ub, img2=ua, label1="Before", label2="After", width=520, in_memory=True)
                except Exception as e:
                    st.error(f"Could not load the comparison images ({type(e).__name__}).")
                st.caption("Slider shows the visible difference between confirmed paired images. "
                           "It does not verify an environmental outcome.")
                with st.expander("Score and Cloudinary URLs"):
                    breakdown_table(p)
                    st.markdown(f"Transformation used for both images: `{media.transformation_for('compare', blur)}`")
                    st.code(f"{ub}\n{ua}", language=None)
                with st.expander("Campaign card"):
                    d0, d1 = (b.get("captured_at") or "")[:10], (a.get("captured_at") or "")[:10]
                    card = media.campaign_card(
                        b, a, headline=b.get("project_name") or "Field work",
                        footer=("Illustrative demo | " if (a.get("synthetic") or b.get("synthetic")) else "")
                        + f"Before {d0 or '?'} | After {d1 or '?'} | visible difference, confirmed pair",
                        blur_faces=blur)
                    if card:
                        st.image(card[0], width="stretch")
                        st.markdown(f"[Open / share image]({card[0]})")
                        st.code(card[1], language=None)
                    else:
                        st.caption("Needs both images on Cloudinary.")
                st.button("Move back to review", key=f"u{p['id']}", icon=":material/undo:",
                          on_click=decide, args=(p, "suggested", "Moved back to review."))

if view == "rejected":
    if not groups["rejected"]:
        st.info("No rejected pairs.")
    for p in groups["rejected"]:
        b, a = assets[p["before_id"]], assets[p["after_id"]]
        with st.container(border=True):
            t1, t2, info, act = st.columns([1, 1, 4, 2], vertical_alignment="center")
            t1.image(media.url_for(b, "thumb", blur_faces=bool(b.get("people_present"))), width=72)
            t2.image(media.url_for(a, "thumb", blur_faces=bool(a.get("people_present"))), width=72)
            info.markdown(f"**{b.get('project_name')}**  \n{dates(p)} · score {p['score']:.2f}")
            act.button("Move back to review", key=f"u{p['id']}", icon=":material/undo:",
                       on_click=decide, args=(p, "suggested", "Moved back to review."))

next_step("Build the impact report", "Turn confirmed pairs into a shareable report.", "Open report", "views/4_Report.py")
