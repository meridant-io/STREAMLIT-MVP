"""Dashboard page – KPIs and quick-look tables."""

import streamlit as st
import pandas as pd
from src.e2caf_client import get_client
from src.sql_templates import q_list_next_usecases, q_list_tags


def render() -> None:
    st.header("📊 Dashboard")

    client = get_client()

    col1, col2 = st.columns(2)

    # ---- Use-case & tag counts --------------------------------------------
    try:
        uc_rows = client.query(q_list_next_usecases())
        uc_df = pd.DataFrame(uc_rows.get("rows", uc_rows.get("data", [])))
        col1.metric("Use Cases", len(uc_df))
    except Exception as e:
        uc_df = pd.DataFrame()
        col1.metric("Use Cases", "—")
        st.warning(f"Could not load use cases: {e}")

    try:
        tag_rows = client.query(q_list_tags())
        tag_df = pd.DataFrame(tag_rows.get("rows", tag_rows.get("data", [])))
        col2.metric("Capability Tags", len(tag_df))
    except Exception as e:
        tag_df = pd.DataFrame()
        col2.metric("Capability Tags", "—")
        st.warning(f"Could not load tags: {e}")

    # ---- Data previews ----------------------------------------------------
    st.divider()

    if not uc_df.empty:
        st.subheader("Use Cases")
        st.dataframe(uc_df, width='stretch')

    if not tag_df.empty:
        st.subheader("Capability Tags")
        st.dataframe(tag_df, width='stretch')


