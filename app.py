from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from src.pages import dashboard, usecase_workspace, architecture

st.set_page_config(page_title="E2CAF Streamlit MVP", layout="wide")

with st.sidebar:
    st.title("E2CAF MVP")
    st.caption("Streamlit UI for E2CAF capability intelligence")
    page = st.radio("Navigate", ["Dashboard", "Use Case Workspace", "Architecture"])

if page == "Dashboard":
    dashboard.render()
elif page == "Use Case Workspace":
    usecase_workspace.render()
elif page == "Architecture":
    architecture.render()
