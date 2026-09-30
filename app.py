"""Ground Truth entry point: defines the multipage navigation."""
import streamlit as st

from gt import db
from gt.ui import boot

boot()
pending = len(db.pairs("suggested"))

pages = {
    "": [st.Page("views/0_Overview.py", title="Home", icon=":material/home:", url_path="overview", default=True)],
    "Step 1 · Collect": [st.Page("views/6_Upload.py", title="Upload photos", icon=":material/add_a_photo:", url_path="upload")],
    "Step 2 · Explore": [st.Page("views/1_Assets.py", title="Evidence library", icon=":material/photo_library:", url_path="assets")],
    "Step 3 · Review": [st.Page("views/3_Pairs.py", title=f"Review pairs ({pending})" if pending else "Review pairs",
                                icon=":material/compare:", url_path="pairs")],
    "Step 4 · Share": [st.Page("views/4_Report.py", title="Impact report", icon=":material/description:", url_path="report")],
    "Check": [st.Page("views/5_Trace.py", title="Trace an image", icon=":material/account_tree:", url_path="trace")],
}
st.navigation(pages).run()
