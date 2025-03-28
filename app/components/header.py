"""
Header component for the FEWS visualization application.
"""
import streamlit as st

def render_header(title: str, version: str):
    """
    Render the application header.
    
    Args:
        title: Application title
        version: Application version
    """
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.title(title)
    
    with col2:
        st.write(f"**Version:** {version}")
        
    st.divider() 