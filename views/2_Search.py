"""Semantic search with filters and a 'why it matched' line."""
import streamlit as st

from gt import ai_provider, config, db, media, search
from gt.ui import AI_BADGE, page_setup

page_setup("Search", "🔎")
st.title("🔎 Search evidence by meaning")


@st.cache_data(show_spinner=False, ttl=3600)
def embed_query(q: str) -> list[float]:
    return ai_provider.embed([q], task="RETRIEVAL_QUERY")[0]


assets = db.assets()
if not assets:
    st.warning("No images loaded yet.")
    st.stop()

examples = ["blocked drain with standing water", "young trees planted in bare soil",
            "freshly repaired road surface", "garbage pile by the roadside"]
query = st.text_input("Describe what you are looking for", placeholder=examples[0])
st.caption("Try: " + " · ".join(f"*{e}*" for e in examples))

projects = {p["id"]: p["name"] for p in db.projects()}
c1, c2 = st.columns(2)
sel_p = c1.multiselect("Project", list(projects), format_func=projects.get)
sel_a = c2.multiselect("Activity (AI-suggested)", sorted({a["activity_type"] for a in assets if a.get("activity_type")}))
pool = [a for a in assets if (not sel_p or a["project_id"] in sel_p) and (not sel_a or a.get("activity_type") in sel_a)]

if not query.strip():
    st.stop()

hits, mode = [], "keyword"
if config.ai_ready():
    try:
        hits = search.semantic_search(embed_query(query.strip()), query, pool)
        mode = "semantic"
    except Exception as e:
        st.warning(f"Semantic search unavailable ({type(e).__name__}); using keyword/tag search instead.")
if mode == "keyword":
    if not config.ai_ready():
        st.info("No AI key configured for this deployment, so search uses **keyword/tag matching** over the "
                "stored AI captions, tags and signals (not semantic embeddings).", icon="ℹ️")
    hits = search.keyword_search(query, pool)

st.caption(f"{len(hits)} result(s) · mode: **{mode}**")
cols = st.columns(4)
for i, h in enumerate(hits):
    a = h["asset"]
    with cols[i % 4]:
        with st.container(border=True):
            st.image(media.url_for(a, "thumb", blur_faces=bool(a.get("people_present"))), width="stretch")
            st.markdown(f"**{a.get('project_name')}** · {(a.get('captured_at') or 'no date')[:10]} · score {h['score']:.2f}")
            st.caption(f"{AI_BADGE}: {a.get('caption') or '—'}")
            st.caption(f"🧭 Why it matched: {h['why']}")
            st.page_link("views/5_Trace.py", label="Trace", icon="🧾", query_params={"asset": a["id"]})
