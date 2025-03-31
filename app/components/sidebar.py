"""
Zijbalk component voor de FEWS visualisatie applicatie.
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
        
        st.markdown("### Over")
        st.markdown(
            """
            Deze applicatie biedt tools voor het visualiseren en analyseren van FEWS-configuraties.
            
            - Bekijk workflows, transformaties en tijdreeksen
            - Analyseer afhankelijkheden tussen entiteiten
            - Identificeer problemen en optimalisatiemogelijkheden
            - Visualiseer het configuratienetwerk
            """
        )
        
        st.divider()
        st.markdown("### Database Verbinding")
        
        # Show database connection status
        if "tools_interface" in st.session_state:
            st.success("✓ Verbonden met database")
        else:
            st.error("✗ Database niet verbonden")
            
        st.divider()
        
        # Add any page-specific controls to the bottom
        return st.container() 