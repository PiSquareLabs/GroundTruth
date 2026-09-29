"""Ground Truth entry point: defines the multipage navigation."""
import streamlit as st

PAGES = [
    st.Page("views/0_Overview.py", title="Overview", icon="🌱", url_path="overview", default=True),
    st.Page("views/1_Assets.py", title="Assets", icon="🗂️", url_path="assets"),
    st.Page("views/2_Search.py", title="Search", icon="🔎", url_path="search"),
    st.Page("views/3_Pairs.py", title="Pairs", icon="🔁", url_path="pairs"),
    st.Page("views/4_Report.py", title="Report", icon="📄", url_path="report"),
    st.Page("views/5_Trace.py", title="Trace", icon="🧾", url_path="trace"),
    st.Page("views/6_Upload.py", title="Upload", icon="⬆️", url_path="upload"),
]

st.navigation(PAGES).run()
