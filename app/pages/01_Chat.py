"""
Chat Interface pagina voor FEWS Netwerkvisualisatie.

Deze pagina biedt een chat-interface voor het stellen van vragen over uw FEWS-configuratie.
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
    page_title="Chat - FEWS Netwerkvisualisatie",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration
config = load_config()

# Render header
render_header(
    title=config.get("app_title", "FEWS Netwerkvisualisatie"),
    version=config.get("app_version", "0.2.0")
)

# Render sidebar
sidebar_container = render_sidebar(page_title="Chat")

# Main content
st.title("Chat Interface")

st.markdown("""
Stel vragen over uw FEWS-configuratie in natuurlijke taal.

Voorbeeldvragen die u kunt stellen:
- Welke workflows zitten in mijn configuratie?
- Hoeveel transformaties zijn er in workflow XYZ?
- Welke tijdreeksen worden geproduceerd door module ABC?
- Vind transformaties gerelateerd aan parameter H.m
- Toon me de afhankelijkheden voor tijdreeks 12345
""")

# Render the chat interface
render_chat_interface(config)

# Render footer
render_footer() 