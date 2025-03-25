"""
Main Streamlit application for FEWS chat.
"""
import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from app.utils import load_config
from app.chat_interface import render_chat_interface

# Application version
APP_VERSION = "0.1.0"

# Set Streamlit theme to light mode - MUST be the first Streamlit command
st.set_page_config(
    page_title=f"FEWS Chat - v{APP_VERSION}",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

def main():
    """Main application entry point."""
    # Load configuration
    config = load_config()
    
    # Main title
    st.title("FEWS Configuratie Chat")
    st.markdown("""
    Stel vragen over je FEWS configuratie in natuurlijke taal.
    De agent helpt je bij het begrijpen van workflows, tijdreeksen, transformaties en hun onderlinge relaties.
    """)
    
    # Render chat interface
    render_chat_interface(config)

if __name__ == "__main__":
    main()
