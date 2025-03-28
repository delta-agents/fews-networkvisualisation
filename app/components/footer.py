"""
Footer component for the FEWS visualization application.
"""
import streamlit as st

def render_footer():
    """
    Render the application footer.
    """
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("FEWS Network Visualization")
    
    with col2:
        st.write("© 2023-2024")
        
    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f8f9fa;
            text-align: center;
            padding: 10px 0;
            font-size: 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    ) 