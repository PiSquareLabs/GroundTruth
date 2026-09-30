"""Evidence library: browse, filter and search photos by meaning."""
from datetime import date

import streamlit as st

from gt import ai_provider, config, db, media, search, trust
from gt.ui import AI_BADGE, next_step, page_header, page_setup, provenance_badge, synthetic_badge

page_setup("Evidence library", ":material/photo_library:")
page_header("Step 2 of 4 · Explore", "Evidence library",
            "Every photo, grouped by project. Search by describing what you want to find.",
            ["Type what you are looking for, like “open drain”. Photos are matched by meaning, not just exact words.",
             "Use Filters to narrow by project or photo type.",
             "Open a photo for details, or Trace to see where it came from."])

EXAMPLES = ["open drain next to a road", "exposed electrical wires", "rusted metal cover", "finished repair"]


@st.cache_data(show_spinner=False, ttl=3600)
def embed_query(q: str) -> list[float]:
    return ai_provider.embed([q], task="RETRIEVAL_QUERY")[0]


assets = db.assets()
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

projects = {p["id"]: p for p in db.projects()}
dates = [date.fromisoformat(a["captured_at"][:10]) for a in assets if a.get("captured_at")]

# The filter widgets live in a popover, whose browser-side widget values can outlast a reset done in a
# callback and come back on the next rerun. So each reset moves them to fresh keys (lib_v) instead.
st.session_state.setdefault("lib_v", 0)


def fkey(name: str) -> str:
    return f"{name}_{st.session_state.lib_v}"


def reset_filters(chosen: list[str] = ()) -> None:
    st.session_state.lib_v += 1
    for pid in projects:
        st.session_state[fkey(f"lib_p_{pid}")] = pid in chosen


# A project chosen on Home arrives as lib_projects; turn it into the per-project checkbox state.
if "lib_projects" in st.session_state:
    reset_filters(st.session_state.pop("lib_projects"))
st.session_state.setdefault("lib_query", "")
st.session_state.setdefault(fkey("lib_role"), "All")
st.session_state.setdefault(fkey("lib_undated"), True)
st.session_state.setdefault(fkey("lib_flagged"), False)
st.session_state.setdefault("blur_faces", True)
role = st.session_state[fkey("lib_role")]
undated = st.session_state[fkey("lib_undated")]
flagged = st.session_state[fkey("lib_flagged")]


def clear_filters() -> None:
    st.session_state.lib_query = ""
    reset_filters()


def pick_example() -> None:
    if st.session_state.get("lib_example"):
        st.session_state.lib_query = st.session_state.lib_example


sel_projects = [pid for pid in projects if st.session_state.get(fkey(f"lib_p_{pid}"))]
n_filters = len(sel_projects) + (role != "All") + (not undated) + flagged

top_l, top_r = st.columns([5, 1], vertical_alignment="bottom")
query = top_l.text_input("Search by describing a photo", key="lib_query", icon=":material/search:",
                         placeholder="e.g. open drain next to a road").strip()
with top_r.popover(f"Filters ({n_filters})" if n_filters else "Filters", icon=":material/tune:", width="stretch"):
    st.markdown("**Project**")
    for pid, p in projects.items():
        st.checkbox(p["name"], key=fkey(f"lib_p_{pid}"))
    st.pills("Photo type", ["All", "Before", "After"], key=fkey("lib_role"), required=True)
    st.checkbox("Include images without a capture date", key=fkey("lib_undated"))
    st.checkbox("Only images with flags", key=fkey("lib_flagged"))
    st.checkbox("Blur faces where people may appear", key="blur_faces",
                help="Uses Cloudinary's e_blur_faces transformation on delivery; the original is not modified.")

st.pills("Try searching for", EXAMPLES, key="lib_example", on_change=pick_example, label_visibility="collapsed")
blur = st.session_state.blur_faces


def keep(a: dict) -> bool:
    if sel_projects and a["project_id"] not in sel_projects:
        return False
    if role != "All" and (a.get("role") or "").lower() != role.lower():
        return False
    if not a.get("captured_at") and not undated:
        return False
    if flagged and not trust.metadata_flags(a):
        return False
    return True


pool = [a for a in assets if keep(a)]
hits, mode = [], None
if query:
    mode = "keyword"
    if config.ai_ready():
        try:
            hits = search.semantic_search(embed_query(query), query, pool)
            mode = "semantic"
        except Exception as e:
            st.warning(f"Semantic search unavailable ({type(e).__name__}); using keyword/tag search instead.")
    if mode == "keyword":
        if not config.ai_ready():
            st.warning("No AI key is configured for this deployment, so search uses **keyword/tag matching** over the "
                       "stored AI captions, tags and signals, not semantic embeddings.")
        hits = search.keyword_search(query, pool)

cap_l, cap_r = st.columns([5, 1], vertical_alignment="center")
if query:
    cap_l.caption(f"{len(hits)} results for “{query}” · matched by {'meaning' if mode == 'semantic' else 'keyword match'}")
else:
    cap_l.caption(f"Showing {len(pool)} of {len(assets)} images")
if query or n_filters:
    cap_r.button("Clear filters", type="tertiary", icon=":material/filter_alt_off:", on_click=clear_filters)


@st.dialog("Photo details", width="large")
def details(a: dict) -> None:
    st.image(media.url_for(a, "display", blur_faces=blur and bool(a.get("people_present"))), width="stretch")
    synthetic_badge(a)
    st.markdown(f"**{(a.get('role') or '').title() + ' · ' if a.get('role') else ''}"
                f"{(a.get('activity_type') or 'unclassified').replace('_', ' ')}** · "
                f"{(a.get('captured_at') or 'no date')[:10]} · {a.get('project_name')}")
    st.markdown(f":violet-badge[{AI_BADGE}] {a.get('caption') or '—'}")
    if a.get("tags"):
        st.caption("Tags: " + ", ".join(a["tags"]))
    for flag in trust.metadata_flags(a):
        st.caption(f":material/warning: {flag}")
    pair = next((p for p in db.pairs() if a["id"] in (p["before_id"], p["after_id"])), None)
    c1, c2 = st.columns(2)
    if c1.button("Open full trace", type="primary", width="stretch"):
        st.switch_page("views/5_Trace.py", query_params={"asset": a["id"]})
    if pair and c2.button("View confirmed pair" if pair["status"] == "confirmed" else "Review its pair", width="stretch"):
        st.session_state.pairs_view = pair["status"]
        st.switch_page("views/3_Pairs.py")


def card(a: dict, hit: dict | None = None) -> None:
    with st.container(border=True):
        st.image(media.url_for(a, "thumb", blur_faces=blur and bool(a.get("people_present"))), width="stretch")
        badges = " ".join(b for b in (provenance_badge(a), f":gray-badge[match {hit['score']:.2f}]" if hit else "") if b)
        if badges:
            st.markdown(badges)
        role = (a.get("role") or "").title()
        activity = (a.get("activity_type") or "unclassified").replace("_", " ")
        st.markdown(f"**{role + ' · ' if role else ''}{activity}** · {(a.get('captured_at') or 'no date')[:10]}")
        if a.get("caption"):
            st.markdown(f":violet-badge[{AI_BADGE}]")
            st.caption(a["caption"])
        if hit:
            st.caption(f":material/explore: **Why it matched:** {hit['why']}")
        for flag in trust.metadata_flags(a):
            st.caption(f":material/warning: {flag}")
        d, t = st.columns(2)
        if d.button("Details", key=f"det_{a['id']}", width="stretch"):
            details(a)
        if t.button("Trace", key=f"tr_{a['id']}", width="stretch"):
            st.switch_page("views/5_Trace.py", query_params={"asset": a["id"]})


if query:
    if not hits:
        st.info("No photos matched. Try different words, or clear the filters.")
    cols = st.columns(4)
    for i, h in enumerate(hits):
        with cols[i % 4]:
            card(h["asset"], h)
else:
    dupes = trust.find_duplicates(assets)
    if dupes:
        with st.expander(f":material/warning: {len(dupes)} possible near-duplicate pair(s)"):
            for x, y, s, how in dupes:
                st.write(f"`{x}` ↔ `{y}` — {how} similarity {s:.3f}")
    if not pool:
        st.info("No photos match these filters.")
    for pid, p in projects.items():
        group = [a for a in pool if a["project_id"] == pid]
        if not group:
            continue
        st.subheader(p["name"])
        st.caption(f"{p.get('location_name') or 'location not set'} · {len(group)} images")
        cols = st.columns(4)
        for i, a in enumerate(group):
            with cols[i % 4]:
                card(a)

next_step("Review before/after pairs", "Confirm which photos show the same spot.", "Review pairs", "views/3_Pairs.py")
