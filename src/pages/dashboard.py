"""Dashboard page – high-level KPIs and summary metrics."""

import streamlit as st


def render() -> None:
    st.header("📊 Dashboard")
    st.write("Welcome to the E2CAF Dashboard.  Key metrics will appear here.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Use Cases", "—")
    col2.metric("Components", "—")
    col3.metric("Health", "—")
