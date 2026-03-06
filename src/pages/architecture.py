import streamlit as st
from pathlib import Path

def render():
    st.title("Platform Architecture")
    img = Path(__file__).resolve().parents[2] / "assets" / "architecture.png"
    if img.exists() and img.stat().st_size > 0:
        st.image(str(img), caption="Architecture overview", use_column_width=True)
    else:
        st.info("Add your architecture diagram to assets/architecture.png")
