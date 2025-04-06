import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import streamlit as st
from utils import load_config
from components.tools_interface import ToolsInterface

from components import (
    init_chat_state,
    render_chat_sidebar,
    render_explore_tab,
    render_reports_tab
)

# Set page config to wide mode
st.set_page_config(layout="wide", page_title="FEWS Network Visualisation")

def init_tools_interface(config):
    """Initialize the tools interface if not already done"""
    if "tools_interface" not in st.session_state:
        try:
            tools = ToolsInterface(db_path=config["db_path"])
            st.session_state.tools_interface = tools
        except Exception as e:
            st.error(f"Error initializing tools interface: {str(e)}")
            return False
    return True

def main():
    # Initialize chat state
    init_chat_state()
    
    # Load configuration from .env
    config = load_config()
    
    # Initialize tools interface
    if not init_tools_interface(config):
        st.error("Failed to initialize tools interface. Please check your configuration.")
        return
    
    # Render chat sidebar with config
    render_chat_sidebar(config)
    
    # Main content area with tabs
    tab1, tab2 = st.tabs(["Explore", "Reports"])
    
    with tab1:
        render_explore_tab()
    
    with tab2:
        render_reports_tab()

if __name__ == "__main__":
    main() 