"""
Home page for FEWS Network Visualization.

This is the main dashboard page for the application.
"""
import streamlit as st
import sys
from pathlib import Path
import os
import asyncio

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar
from app.utils.tools_interface import ToolsInterface

# Set Streamlit page configuration
st.set_page_config(
    page_title="FEWS Network Visualization",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration
config = load_config()

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

# Initialize session state
if "tools_interface" not in st.session_state:
    try:
        tools_interface = ToolsInterface(
            db_path=config["db_path"],
            log_dir=config["log_dir"]
        )
        tools_interface.connect()
        st.session_state.tools_interface = tools_interface
    except Exception as e:
        st.error(f"Failed to initialize tools interface: {str(e)}")

# Render header
render_header(
    title=config.get("app_title", "FEWS Network Visualization"),
    version=config.get("app_version", "0.2.0")
)

# Render sidebar
sidebar_container = render_sidebar(page_title="Home")

# Main content
st.markdown(
    """
    ## Welcome to FEWS Network Visualization
    
    This application helps you analyze and visualize your FEWS configuration.
    
    ### Key Features
    
    - **Chat Interface**: Ask questions about your FEWS configuration
    - **Search and Exploration**: Find specific workflows, time series, and transformations
    - **Detailed Views**: Examine workflows, transformations, and time series
    - **Dependency Analysis**: Analyze relationships between configuration elements
    - **Health Checks**: Identify issues and optimization opportunities
    """
)

# Database summary
if "tools_interface" in st.session_state:
    tools = st.session_state.tools_interface
    
    st.markdown("## Database Summary")
    
    with st.spinner("Loading database statistics..."):
        try:
            # Execute queries to get statistics directly using the db_connection
            if tools.db_connection:
                # Create cursor
                cursor = tools.db_connection.cursor()
                
                # Get counts
                cursor.execute("SELECT COUNT(*) as count FROM call_stacks")
                workflow_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) as count FROM ts_sets")
                timeseries_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) as count FROM trafos")
                transformation_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) as count FROM links")
                link_count = cursor.fetchone()[0]
                
                # Display statistics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Workflows", workflow_count)
                
                with col2:
                    st.metric("Time Series", timeseries_count)
                
                with col3:
                    st.metric("Transformations", transformation_count)
                
                with col4:
                    st.metric("Links", link_count)
            else:
                st.warning("Database connection not initialized properly.")
                
            # Quick access to analysis tools
            st.markdown("## Quick Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("### Chat & Search")
                st.markdown("- [💬 Chat Interface](01_Chat)")
                st.markdown("- [🔍 Search and Exploration](02_Search_and_Exploration)")
            
            with col2:
                st.markdown("### Analysis")
                st.markdown("- [🔗 Dependency Analysis](03_Dependency_Analysis)")
                st.markdown("- [🔬 Health Check](04_Health_Check)")
            
            with col3:
                st.markdown("### Setup")
                st.markdown("- [⚙️ Settings](05_Settings)")
                st.markdown("- [📊 Documentation](https://github.com/yourusername/fews-networkvisualisation)")
                st.markdown("<small>Documentation opens in a new tab</small>", unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Error loading database statistics: {str(e)}")
else:
    st.warning("Database connection not available. Please check your configuration.")

# Render footer
render_footer() 