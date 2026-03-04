import streamlit as st
from src.e2caf_client import get_client

def render():
    st.title("E2CAF Platform — Dashboard")
    client = get_client()
    st.subheader("API Health")

    try:
        health = client.health()
        st.success("API reachable")
        st.json(health)
    except Exception as e:
        st.error(f"Health check failed: {e}")
