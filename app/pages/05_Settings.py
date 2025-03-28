"""
Settings page for FEWS Network Visualization.

This page provides configuration options for the application.
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
    page_title="Settings - FEWS Network Visualization",
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
    title=config.get("app_title", "FEWS Network Visualization"),
    version=config.get("app_version", "0.2.0")
)

# Render sidebar
sidebar_container = render_sidebar(page_title="Settings")

# Main content
st.title("Settings")

st.markdown("""
Configure application settings and manage connections.
""")

# Connection settings
st.header("Database Connection")

db_path = st.text_input("Database Path", value=config.get("db_path", ""), help="Path to the FEWS configuration database")
log_dir = st.text_input("Log Directory", value=config.get("log_dir", ""), help="Directory for logs")

if st.button("Update Connection"):
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
    
    st.success("Connection settings updated. Restarting connection...")
    time.sleep(1)
    st.rerun()

# Application settings
st.header("Application Settings")

app_title = st.text_input("Application Title", value=config.get("app_title", "FEWS Network Visualization"))
app_version = st.text_input("Application Version", value=config.get("app_version", "0.2.0"))

if st.button("Update Application Settings"):
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
    
    st.success("Application settings updated. Please refresh the page to see changes.")

# Connection status
st.header("Connection Status")

if "tools_interface" in st.session_state:
    st.success("✓ Connected to database")
    
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
                
                st.markdown("### Database Stats")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Workflows", stats["workflow_count"])
                
                with col2:
                    st.metric("Time Series", stats["timeseries_count"])
                
                with col3:
                    st.metric("Transformations", stats["transformation_count"])
                
                with col4:
                    st.metric("Links", stats["link_count"])
        except Exception as e:
            st.error(f"Error retrieving database stats: {str(e)}")
    except Exception as e:
        st.error(f"Error retrieving database information: {str(e)}")
    
    # Add a button to close the connection
    if st.button("Close Connection"):
        st.session_state.tools_interface.close()
        st.session_state.pop("tools_interface")
        st.success("Connection closed.")
        time.sleep(1)
        st.rerun()
else:
    st.error("✗ Database not connected")
    
    # Add a button to initialize the connection
    if st.button("Initialize Connection"):
        try:
            from app.utils.tools_interface import ToolsInterface
            
            tools_interface = ToolsInterface(
                db_path=config["db_path"],
                log_dir=config["log_dir"]
            )
            tools_interface.connect()
            st.session_state.tools_interface = tools_interface
            
            st.success("Connection initialized successfully.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to initialize connection: {str(e)}")

# Render footer
render_footer() 