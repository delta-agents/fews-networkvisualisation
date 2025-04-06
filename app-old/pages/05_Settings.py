"""
Instellingen pagina voor FEWS Netwerkvisualisatie.

Deze pagina biedt configuratieopties voor de applicatie.
"""
import streamlit as st
from pathlib import Path
import sys
import os
import time
import asyncio

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar

# Set page configuration
st.set_page_config(
    page_title="Instellingen - FEWS Netwerkvisualisatie",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

# Load configuration
config = load_config()

# Render header
render_header(
    title=config.get("app_title", "FEWS Netwerkvisualisatie"),
    version=config.get("app_version", "0.2.0")
)

# Render sidebar
sidebar_container = render_sidebar(page_title="Instellingen")

# Main content
st.title("Instellingen")

st.markdown("""
Configureer applicatie-instellingen en beheer verbindingen.
""")

# Connection settings
st.header("Database Verbinding")

db_path = st.text_input("Database Pad", value=config.get("db_path", ""), help="Pad naar de FEWS-configuratie database")
log_dir = st.text_input("Log Map", value=config.get("log_dir", ""), help="Map voor logbestanden")

if st.button("Verbinding Bijwerken"):
    # Write configuration to .env file
    env_path = Path(__file__).parent.parent.parent / "env" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(env_path, "w") as f:
        f.write(f"FEWS_DB_PATH={db_path}\n")
        f.write(f"FEWS_LOG_DIR={log_dir}\n")
    
    # Reinitialize tools interface
    if "tools_interface" in st.session_state:
        st.session_state.tools_interface.close()
        st.session_state.pop("tools_interface")
    
    st.success("Verbindingsinstellingen bijgewerkt. Verbinding opnieuw starten...")
    time.sleep(1)
    st.rerun()

# Application settings
st.header("Applicatie Instellingen")

app_title = st.text_input("Applicatie Titel", value=config.get("app_title", "FEWS Netwerkvisualisatie"))
app_version = st.text_input("Applicatie Versie", value=config.get("app_version", "0.2.0"))

if st.button("Applicatie Instellingen Bijwerken"):
    # Write configuration to .env file
    env_path = Path(__file__).parent.parent.parent / "env" / ".env"
    
    # Read existing config to preserve it
    env_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = [line.strip() for line in f.readlines()]
    
    # Update or add settings
    settings = {
        "FEWS_APP_TITLE": app_title,
        "FEWS_APP_VERSION": app_version
    }
    
    # Update existing lines or prepare to add new ones
    new_lines = []
    for line in env_lines:
        for key, value in settings.items():
            if line.startswith(f"{key}="):
                line = f"{key}={value}"
                settings.pop(key)
                break
        new_lines.append(line)
    
    # Add any remaining settings
    for key, value in settings.items():
        new_lines.append(f"{key}={value}")
    
    # Write updated config
    with open(env_path, "w") as f:
        f.write("\n".join(new_lines))
    
    st.success("Applicatie-instellingen bijgewerkt. Vernieuw de pagina om de wijzigingen te zien.")

# Connection status
st.header("Verbindingsstatus")

if "tools_interface" in st.session_state:
    st.success("✓ Verbonden met database")
    
    # Show database information
    try:
        # Execute query to get database statistics
        query = """
        SELECT 
            (SELECT COUNT(*) FROM call_stacks) AS workflow_count,
            (SELECT COUNT(*) FROM ts_sets) AS timeseries_count,
            (SELECT COUNT(*) FROM trafos) AS transformation_count,
            (SELECT COUNT(*) FROM links) AS link_count
        """
        
        # Run the query and display stats
        try:
            results = run_async_function(
                st.session_state.tools_interface.execute_custom_query,
                query=query
            )
            
            if results and results.results:
                stats = results.results[0]
                
                st.markdown("### Database Statistieken")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Workflows", stats["workflow_count"])
                
                with col2:
                    st.metric("Tijdreeksen", stats["timeseries_count"])
                
                with col3:
                    st.metric("Transformaties", stats["transformation_count"])
                
                with col4:
                    st.metric("Koppelingen", stats["link_count"])
        except Exception as e:
            st.error(f"Fout bij ophalen database statistieken: {str(e)}")
    except Exception as e:
        st.error(f"Fout bij ophalen database informatie: {str(e)}")
    
    # Add a button to close the connection
    if st.button("Sluit Verbinding"):
        st.session_state.tools_interface.close()
        st.session_state.pop("tools_interface")
        st.success("Verbinding gesloten.")
        time.sleep(1)
        st.rerun()
else:
    st.error("✗ Database niet verbonden")
    
    # Add a button to initialize the connection
    if st.button("Initialiseer Verbinding"):
        try:
            from app.utils.tools_interface import ToolsInterface
            
            tools_interface = ToolsInterface(
                db_path=config["db_path"],
                log_dir=config["log_dir"]
            )
            tools_interface.connect()
            st.session_state.tools_interface = tools_interface
            
            st.success("Verbinding succesvol geïnitialiseerd.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Kon verbinding niet initialiseren: {str(e)}")

# Render footer
render_footer() 