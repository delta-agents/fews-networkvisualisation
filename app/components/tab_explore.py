import streamlit as st
import pandas as pd
from datetime import datetime

from .sidebar_chat import add_to_chat

def load_workflow_data():
    """Load workflow data using the search_workflows function"""
    try:
        # Check if tools interface is available
        if "tools_interface" not in st.session_state:
            st.error("Database connection not available. Please check your configuration.")
            return pd.DataFrame()
            
        # Use the tools interface from session state
        tools = st.session_state.tools_interface
        
        # Use '%' as default pattern to get all workflows
        results = tools.search_workflows(name_pattern='%')
        
        if results and hasattr(results, 'results'):
            data = []
            for workflow in results.results:
                data.append({
                    "ID": workflow.id,  # Hidden column
                    "Workflow ID": workflow.wf_id,
                    "Beschrijving": workflow.desc,
                    "Module Config IDs": ', '.join(workflow.module_config_ids) if workflow.module_config_ids else 'Geen'
                })
            return pd.DataFrame(data)
        return pd.DataFrame()  # Return empty DataFrame if no results
    except Exception as e:
        st.error(f"Error loading workflows: {str(e)}")
        return pd.DataFrame()

def render_explore_tab():
    """Render the explore tab content with workflow data"""
    st.header("Explore Workflows")
    
    # Load workflow data
    df = load_workflow_data()
    
    if df.empty:
        st.warning("No workflows found or error loading workflows.")
        return
    
    # Define which columns to display
    display_columns = ["Workflow ID", "Beschrijving", "Module Config IDs"]
    
    # Add search functionality
    search_term = st.text_input("Search workflows", "")
    
    # Filter dataframe based on search term
    if search_term:
        # Search in all columns, including hidden ones
        mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        filtered_df = df[mask]
    else:
        filtered_df = df

    # Add header row
    with st.container():
        header_cols = st.columns([0.15] + [1] * len(display_columns))
        header_cols[0].markdown("")
        for i, col_name in enumerate(display_columns):
            header_cols[i+1].markdown(f"**{col_name}**")
        st.divider()        
    
    # Create a container for each row with hover effect
    for idx, row in filtered_df.iterrows():
        with st.container():
            # Create columns only for displayed columns plus the chat button
            cols = st.columns([0.15] + [1] * len(display_columns))
            
            # Add to chat button
            if cols[0].button("💬", key=f"btn_{idx}", use_container_width=True):
                # Add the workflow type to the dictionary
                workflow_data = row.to_dict()  # This includes all columns, even hidden ones
                workflow_data["type"] = "workflow"
                add_to_chat(workflow_data)
            
            # Display only the visible columns
            for i, col_name in enumerate(display_columns, 1):
                cols[i].write(row[col_name])
            
            # Add a subtle divider
            st.divider()
    
    # Show result count
    st.markdown(f"**{len(filtered_df)} workflows found**" + 
               (f" (filtered from {len(df)} total)" if search_term else "")) 