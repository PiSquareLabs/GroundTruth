"""Ground Truth entry point: defines the multipage navigation."""
import streamlit as st

PAGES = [
    st.Page("pages/0_Overview.py", title="Overview", icon="🌱", url_path="overview", default=True),
    st.Page("pages/1_Assets.py", title="Assets", icon="🗂️", url_path="assets"),
    st.Page("pages/2_Search.py", title="Search", icon="🔎", url_path="search"),
    st.Page("pages/5_Trace.py", title="Trace", icon="🧾", url_path="trace"),
    st.Page("pages/6_Upload.py", title="Upload", icon="⬆️", url_path="upload"),
]

st.navigation(PAGES).run()
