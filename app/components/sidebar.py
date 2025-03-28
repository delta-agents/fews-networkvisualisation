"""
Sidebar component for the FEWS visualization application.
"""
import streamlit as st

def render_sidebar(page_title=None):
    """
    Render the application sidebar.
    
    Args:
        page_title: Optional title of the current page
    """
    with st.sidebar:
        if page_title:
            st.header(page_title)
        
        st.markdown("### About")
        st.markdown(
            """
            This application provides tools for visualizing and analyzing FEWS configurations.
            
            - View workflows, transformations, and time series
            - Analyze dependencies between entities
            - Identify issues and optimization opportunities
            - Visualize the configuration network
            """
        )
        
        st.divider()
        st.markdown("### Database Connection")
        
        # Show database connection status
        if "tools_interface" in st.session_state:
            st.success("✓ Connected to database")
        else:
            st.error("✗ Database not connected")
            
        st.divider()
        
        # Add any page-specific controls to the bottom
        return st.container() 