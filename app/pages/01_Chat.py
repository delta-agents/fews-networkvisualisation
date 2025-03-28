"""
Chat Interface page for FEWS Network Visualization.

This page provides a chat interface for asking questions about your FEWS configuration.
"""
import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar
from app.chat_interface import render_chat_interface

# Set page configuration
st.set_page_config(
    page_title="Chat - FEWS Network Visualization",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration
config = load_config()

# Render header
render_header(
    title=config.get("app_title", "FEWS Network Visualization"),
    version=config.get("app_version", "0.2.0")
)

# Render sidebar
sidebar_container = render_sidebar(page_title="Chat")

# Main content
st.title("Chat Interface")

st.markdown("""
Ask questions about your FEWS configuration in natural language.

Example questions you can ask:
- What workflows are in my configuration?
- How many transformations are in workflow XYZ?
- What time series are produced by module ABC?
- Find transformations related to parameter H.m
- Show me the dependencies for time series 12345
""")

# Render the chat interface
render_chat_interface(config)

# Render footer
render_footer() 