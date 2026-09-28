"""Ground Truth entry point: defines the multipage navigation."""
import streamlit as st

PAGES = [
    st.Page("pages/0_Overview.py", title="Overview", icon="🌱", url_path="overview", default=True),
    st.Page("pages/1_Assets.py", title="Assets", icon="🗂️", url_path="assets"),
    st.Page("pages/5_Trace.py", title="Trace", icon="🧾", url_path="trace"),
]

st.navigation(PAGES).run()
