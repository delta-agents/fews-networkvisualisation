"""
Search and Exploration page for FEWS Network Visualization.

This page provides access to search for workflows, time series, and transformations.
"""
import streamlit as st
import asyncio
import pandas as pd
from pathlib import Path
import sys
import random
import re
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from streamlit import components

# Add a function to render Mermaid diagrams
def render_mermaid(mermaid_code, height=200):
    """
    Renders a Mermaid diagram from the provided code using JavaScript.
    
    Args:
        mermaid_code: The Mermaid diagram code to render
        height: Optional height in pixels (default: 200)
    """
    # Create a unique ID for this diagram
    diagram_id = f"mermaid-diagram-{random.randint(1, 100000)}"
    
    # HTML with embedded Mermaid JS
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                mermaid.initialize({{ 
                    startOnLoad: true,
                    // Use more compact styling
                    themeVariables: {{
                        nodePadding: 4,
                        nodeSpacing: 20,
                        rankSpacing: 20,
                        labelMargin: 2
                    }}
                }});
            }});
        </script>
        <style>
            .mermaid {{
                width: 100%;
                overflow: visible;
            }}
            /* Make text smaller in the diagram */
            .mermaid .label {{
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid" id="{diagram_id}">
            {mermaid_code}
        </div>
    </body>
    </html>
    """
    
    # Render the HTML with custom height
    components.v1.html(html, height=height)

# Helper function to estimate diagram height based on content complexity
def estimate_diagram_height(mermaid_code):
    """
    Estimate an appropriate height for the diagram based on its complexity.
    
    Args:
        mermaid_code: The Mermaid diagram code
        
    Returns:
        Estimated height in pixels
    """
    # Count input and output time series connections
    lines = mermaid_code.strip().split('\n')
    
    # Look for edges connecting to time series
    in_ts_count = 0
    out_ts_count = 0
    
    for line in lines:
        # Check for input time series (edges ending at ts_)
        if re.search(r'\w+\s*-->\s*ts_\d+', line):
            in_ts_count += 1
        # Check for output time series (edges starting from ts_)
        if re.search(r'ts_\d+\s*-->', line):
            out_ts_count += 1
    
    # Use the maximum count of input or output time series
    ts_count = max(in_ts_count, out_ts_count)
    
    # Calculate height based on time series count with lower values
    height_per_ts = 20
    base_height = 15
    
    # If no time series found, fall back to node counting method
    if ts_count == 0:
        node_count = sum(1 for line in lines if re.search(r'\w+(\[.*?\]|\(.*?\)|\>.*?\]|\{.*?\})', line))
        edge_count = sum(1 for line in lines if re.search(r'\w+\s*-->', line))
        height = base_height + (node_count + edge_count) * 10
    else:
        height = base_height + ts_count * height_per_ts
    
    # Ensure reasonable bounds on height
    return max(150, min(height, 600))

# Add function to enhance mermaid diagrams with more detailed information
def enhance_mermaid_diagram(mermaid_code, details=None):
    """
    Enhances a mermaid diagram by adding more detailed information about entities.
    
    Args:
        mermaid_code: The original mermaid diagram code
        details: Optional details object containing additional information
        
    Returns:
        Enhanced mermaid diagram code
    """
    # Parse the mermaid code to identify nodes
    lines = mermaid_code.strip().split('\n')
    enhanced_lines = []
    
    # Cache for already fetched details to avoid duplicate API calls
    timeseries_cache = {}
    transformation_cache = {}
    
    for line in lines:
        enhanced_line = line
        
        # Check if this is a node definition line
        node_match = re.search(r'(\w+)(\[.*?\]|\(.*?\)|\>.*?\]|\{.*?\})', line)
        if node_match:
            node_id = node_match.group(1).strip()
            
            # Check if this is a time series node (typically starts with "ts_")
            if node_id.startswith("ts_"):
                try:
                    # Extract the time series ID from the node ID
                    ts_id = int(node_id.replace("ts_", ""))
                    
                    # Use cached data if available
                    if ts_id in timeseries_cache:
                        ts_info = timeseries_cache[ts_id]
                    else:
                        # Use describe_timeseries tool instead of custom SQL
                        ts_details = run_async_search(
                            st.session_state.tools_interface.describe_timeseries,
                            timeseries_id=ts_id,
                            include_transformations=False  # Just need basic info
                        )
                        
                        if ts_details and ts_details.results:
                            ts_info = ts_details.results[0]
                            # Cache the result
                            timeseries_cache[ts_id] = ts_info
                        else:
                            # No details available, keep original line
                            enhanced_lines.append(line)
                            continue
                    
                    # Create a detailed label
                    detailed_label = f"{ts_info.modins}•{ts_info.vtype}•{ts_info.parid}•{ts_info.qualifiers or ''}•{ts_info.tstype}•{ts_info.timess}"
                    
                    # Replace the existing label with the detailed one
                    if "[" in line:
                        enhanced_line = re.sub(r'(\w+)(\[.*?\])', f"\\1[{detailed_label}]", line)
                    elif "(" in line:
                        enhanced_line = re.sub(r'(\w+)(\(.*?\))', f"\\1({detailed_label})", line)
                    elif "{" in line:
                        enhanced_line = re.sub(r'(\w+)(\{.*?\})', f"\\1{{{detailed_label}}}", line)
                except Exception as e:
                    # If anything fails, keep the original line
                    pass
            
            # Check if this is a transformation node (typically starts with "trafo_")
            elif node_id.startswith("trafo_"):
                try:
                    # Extract the transformation ID from the node ID
                    trafo_id = int(node_id.replace("trafo_", ""))
                    
                    # Use cached data if available
                    if trafo_id in transformation_cache:
                        trafo_info = transformation_cache[trafo_id]
                    else:
                        # Check if details were provided (optimization)
                        if details and details.results and details.results[0].id == trafo_id:
                            trafo_info = details.results[0]
                        else:
                            # Use get_transformation_details tool
                            trafo_details = run_async_search(
                                st.session_state.tools_interface.get_transformation_details,
                                transformation_id=trafo_id
                            )
                            
                            if trafo_details and trafo_details.results:
                                trafo_info = trafo_details.results[0]
                                # Cache the result
                                transformation_cache[trafo_id] = trafo_info
                            else:
                                # No details available, keep original line
                                enhanced_lines.append(line)
                                continue
                    
                    # Create a detailed label with description and module config
                    detailed_label = f"{trafo_info.desc} (Module: {trafo_info.modins}, Order: {trafo_info.ord_nr})"
                    
                    # Replace the existing label with the detailed one
                    if "[" in line:
                        enhanced_line = re.sub(r'(\w+)(\[.*?\])', f"\\1[{detailed_label}]", line)
                    elif "(" in line:
                        enhanced_line = re.sub(r'(\w+)(\(.*?\))', f"\\1({detailed_label})", line)
                    elif "{" in line:
                        enhanced_line = re.sub(r'(\w+)(\{.*?\})', f"\\1{{{detailed_label}}}", line)
                except Exception as e:
                    # If anything fails, keep the original line
                    pass
        
        enhanced_lines.append(enhanced_line)
    
    return '\n'.join(enhanced_lines)

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar
from app.utils.tools_interface import ToolsInterface

# Set page configuration
st.set_page_config(
    page_title="Search and Exploration - FEWS Network Visualization",
    page_icon="🔍",
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
sidebar_container = render_sidebar(page_title="Search & Exploration")

def run_async_search(search_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(search_function(**kwargs))
    finally:
        loop.close()

def display_timeseries_results(results):
    """Display time series search results."""
    st.markdown(results.markdown_content)
    
    if results.results:
        # Convert results to DataFrame for better display
        data = []
        for ts in results.results:
            data.append({
                "ID": ts.id,
                "Module": ts.modins,
                "Parameter": ts.parid,
                "Qualifiers": ts.qualifiers,
                "Type": ts.tstype,
                "Time Step": ts.timess,
                "Value Type": ts.vtype
            })
        
        df = pd.DataFrame(data)
        
        # Add filter options
        col1, col2 = st.columns(2)
        with col1:
            if len(df["Module"].unique()) > 1:
                module_filter = st.multiselect(
                    "Filter by Module",
                    options=sorted(df["Module"].unique()),
                    default=[]
                )
            else:
                module_filter = []
                
        with col2:
            if len(df["Parameter"].unique()) > 1:
                parameter_filter = st.multiselect(
                    "Filter by Parameter",
                    options=sorted(df["Parameter"].unique()),
                    default=[]
                )
            else:
                parameter_filter = []
        
        # Apply filters
        filtered_df = df.copy()
        if module_filter:
            filtered_df = filtered_df[filtered_df["Module"].isin(module_filter)]
        if parameter_filter:
            filtered_df = filtered_df[filtered_df["Parameter"].isin(parameter_filter)]
        
        # Add sorting options
        sort_column = st.selectbox("Sort by", df.columns.tolist(), key="timeseries_sort")
        sort_ascending = st.checkbox("Ascending order", True, key="timeseries_sort_order")
        
        # Sort and display as table
        filtered_df_sorted = filtered_df.sort_values(by=sort_column, ascending=sort_ascending)
        st.dataframe(filtered_df_sorted, use_container_width=True)
        
        # Add metrics about the results
        st.markdown(f"**Found {len(filtered_df)} time series** (filtered from {len(df)} total results)")
        
        # Download option
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download filtered results as CSV",
            data=csv,
            file_name="timeseries_search_results.csv",
            mime="text/csv"
        )
        
        # View details options
        st.subheader("View Time Series Details")
        
        # Create a callback function to update the details view when selection changes
        def on_timeseries_select():
            st.session_state.selected_timeseries_id = st.session_state.timeseries_selector
            st.session_state.timeseries_details_view_active = True
            
        # Use the on_change parameter to trigger the update when selection changes
        selected_timeseries = st.selectbox(
            "Select a time series to view details",
            options=filtered_df["ID"].tolist(),
            format_func=lambda x: f"{x} - {filtered_df.loc[filtered_df['ID'] == x, 'Parameter'].iloc[0]} ({filtered_df.loc[filtered_df['ID'] == x, 'Module'].iloc[0]})",
            key="timeseries_selector",
            on_change=on_timeseries_select
        )
        
        # Remove the View Details button
    else:
        st.info("No time series found matching your criteria.")

def display_transformation_results(results):
    """Display transformation search results."""
    # Remove the markdown table display
    
    if results.results:
        # Convert results to DataFrame for better display
        data = []
        for trafo in results.results:
            data.append({
                "Workflow": trafo.workflow_name,
                "Module Config": trafo.modins,
                "Transformation": trafo.id,
                "Order": trafo.ord_nr,
                "Description": trafo.desc
            })
        
        df = pd.DataFrame(data)
        
        # Add filter options
        col1, col2 = st.columns(2)
        with col1:
            if len(df["Module Config"].unique()) > 1:
                module_filter = st.multiselect(
                    "Filter by Module Config",
                    options=sorted(df["Module Config"].unique()),
                    default=[]
                )
            else:
                module_filter = []
                
        with col2:
            if len(df["Workflow"].unique()) > 1:
                workflow_filter = st.multiselect(
                    "Filter by Workflow",
                    options=sorted(df["Workflow"].unique()),
                    default=[]
                )
            else:
                workflow_filter = []
        
        # Apply filters
        filtered_df = df.copy()
        if module_filter:
            filtered_df = filtered_df[filtered_df["Module Config"].isin(module_filter)]
        if workflow_filter:
            filtered_df = filtered_df[filtered_df["Workflow"].isin(workflow_filter)]
        
        # Add sorting options
        sort_column = st.selectbox("Sort by", df.columns.tolist(), key="transformation_sort")
        sort_ascending = st.checkbox("Ascending order", True, key="transformation_sort_order")
        
        # Sort and display as table
        filtered_df_sorted = filtered_df.sort_values(by=sort_column, ascending=sort_ascending)
        st.dataframe(filtered_df_sorted, use_container_width=True)
        
        # Add metrics about the results
        st.markdown(f"**Found {len(filtered_df)} transformations** (filtered from {len(df)} total results)")
        
        # Download option
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download filtered results as CSV",
            data=csv,
            file_name="transformation_search_results.csv",
            mime="text/csv"
        )
        
        # View details options
        st.subheader("View Transformation Details")
        
        # Create a callback function to update the details view when selection changes
        def on_transformation_select():
            st.session_state.selected_transformation_id = st.session_state.transformation_selector
            st.session_state.transformation_details_view_active = True
            
        # Use the on_change parameter to trigger the update when selection changes
        selected_transformation = st.selectbox(
            "Select a transformation to view details",
            options=filtered_df["Transformation"].tolist(),
            format_func=lambda x: f"{x} - {filtered_df.loc[filtered_df['Transformation'] == x, 'Description'].iloc[0]}",
            key="transformation_selector",
            on_change=on_transformation_select
        )
        
        # Remove the View Details button
    else:
        st.info("No transformations found matching your criteria.")

# Main content
st.title("Search and Exploration")

# Check if tools interface is available
if "tools_interface" not in st.session_state:
    st.error("Database connection not available. Please check your configuration.")
    render_footer()
    st.stop()

# Use tabs for different search types
tab1, tab2, tab3 = st.tabs(["Workflow Search", "Time Series Search", "Transformation Search"])

with tab1:
    st.header("Search Workflows")
    
    st.write("Enter search terms below to find workflows. Results will update automatically as you type.")
    
    workflow_name = st.text_input("Workflow Name or Description", key="workflow_name", 
                                  help="Enter a pattern to match workflow names or descriptions")
    
    # Create a container for the results
    workflow_results_container = st.container()
    
    # Auto-search function that runs when inputs change
    def search_workflows():
        with workflow_results_container:
            with st.spinner("Searching workflows..."):
                try:
                    # Use '%' as the default pattern if empty
                    pattern = workflow_name if workflow_name else "%"
                    results = run_async_search(
                        st.session_state.tools_interface.search_workflows,
                        name_pattern=pattern
                    )
                    
                    if results.results:
                        # Convert results to DataFrame for better display
                        data = []
                        for workflow in results.results:
                            data.append({
                                "ID": workflow.id,
                                "Workflow ID": workflow.wf_id,
                                "Description": workflow.desc,
                                "Module Config IDs": ', '.join(workflow.module_config_ids) if workflow.module_config_ids else 'None'
                            })
                        
                        df = pd.DataFrame(data)
                        
                        # Add sorting options
                        sort_column = st.selectbox("Sort by", ["ID", "Workflow ID", "Description", "Module Config IDs"], key="workflow_sort")
                        sort_ascending = st.checkbox("Ascending order", True, key="workflow_sort_order")
                        
                        # Sort and display as table
                        df_sorted = df.sort_values(by=sort_column, ascending=sort_ascending)
                        st.dataframe(df_sorted, use_container_width=True)
                        
                        # Download option
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download results as CSV",
                            data=csv,
                            file_name="workflow_search_results.csv",
                            mime="text/csv"
                        )
                        
                        # View details options
                        st.subheader("View Workflow Details")
                        
                        # Create a callback function to update the details view when selection changes
                        def on_workflow_select():
                            st.session_state.selected_workflow_id = st.session_state.workflow_selector
                            st.session_state.workflow_details_view_active = True
                            
                        # Use the on_change parameter to trigger the update when selection changes
                        selected_workflow = st.selectbox(
                            "Select a workflow to view details",
                            options=df["ID"].tolist(),
                            format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Workflow ID'].iloc[0]}",
                            key="workflow_selector",
                            on_change=on_workflow_select
                        )
                    else:
                        st.info(f"No workflows found matching the pattern '{pattern}'.")
                except Exception as e:
                    st.error(f"Error searching workflows: {str(e)}")
    
    # Trigger search automatically whenever the input changes
    if "prev_workflow_name" not in st.session_state:
        st.session_state.prev_workflow_name = ""
    
    # Check if the input has changed
    if workflow_name != st.session_state.prev_workflow_name:
        st.session_state.prev_workflow_name = workflow_name
        search_workflows()
    else:
        search_workflows()
    
    # Display workflow details if requested
    if "workflow_details_view_active" in st.session_state and st.session_state.workflow_details_view_active:
        st.header("Workflow Details")
        
        with st.spinner("Loading workflow details..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.get_workflow_details,
                    workflow_id=st.session_state.selected_workflow_id
                )
                
                # Extract workflow details directly from the results
                workflow = details.results[0]
                
                # Display the workflow structure directly with the diagram
                st.markdown("### Workflow Structure")
                
                try:
                    # Create nodes for the flow diagram
                    nodes = []
                    edges = []
                    
                    # 1. Add workflow node (starting node)
                    workflow_node = StreamlitFlowNode(
                        id=str(workflow.id),
                        pos=(100, 100),
                        data={'content': workflow.wf_id, 'description': workflow.desc},
                        node_type='input',
                        source_position='right',
                        draggable=False
                    )
                    nodes.append(workflow_node)
                    
                    # 2. Add module nodes
                    module_y = 50
                    module_y_step = 100
                    
                    for i, module_call in enumerate(workflow.module_calls):
                        module_id = f"module_{module_call.mic_id}"
                        module_name = module_call.modins
                        
                        # Position modules vertically
                        y_pos = module_y + i * module_y_step
                        
                        # Add module node
                        module_node = StreamlitFlowNode(
                            id=module_id,
                            pos=(350, y_pos),
                            data={'content': module_name},
                            node_type='default',
                            source_position='right',
                            target_position='left',
                            draggable=False
                        )
                        nodes.append(module_node)
                        
                        # Add edge from workflow to module
                        edge = StreamlitFlowEdge(
                            id=f"edge_wf_to_{module_id}",
                            source=str(workflow.id),
                            target=module_id,
                            animated=True,
                            marker_end={'type': 'arrow'}
                        )
                        edges.append(edge)
                    
                    # Create a proper flow id
                    flow_key = f"workflow_flow_{workflow.id}"
                    
                    # Initialize the state if it doesn't exist in session state
                    if flow_key not in st.session_state:
                        st.session_state[flow_key] = StreamlitFlowState(nodes, edges)
                    
                    # Capture the updated state with selected node/edge
                    updated_state = streamlit_flow(
                        flow_key,
                        st.session_state[flow_key],
                        fit_view=True,
                        show_controls=True,
                        show_minimap=False,
                        height=500,
                        get_node_on_click=True,
                        get_edge_on_click=True
                    )
                    
                    # Display which node was selected if any
                    if updated_state and updated_state.selected_id:
                        selected_node_id = updated_state.selected_id
                        st.write(f"### Selected: {selected_node_id}")
                        
                        # Check if the selected node is the workflow
                        if selected_node_id == str(workflow.id):
                            st.write("#### Workflow Details")
                            st.write(f"**ID:** {workflow.id}")
                            st.write(f"**Name:** {workflow.wf_id}")
                            st.write(f"**Description:** {workflow.desc}")
                            st.write(f"**Function:** {workflow.wffn}")
                            
                        # Check if the selected node is a module
                        elif selected_node_id.startswith("module_"):
                            module_id = int(selected_node_id.replace("module_", ""))
                            module = next((m for m in workflow.module_calls if m.mic_id == module_id), None)
                            
                            if module:
                                st.write("#### Module Details")
                                st.write(f"**ID:** {module.mic_id}")
                                st.write(f"**Name:** {module.modins}")
                                st.write(f"**Order:** {module.ord_nr}")
                                
                                # Directly show transformations for this module
                                st.write("#### Transformations in this module:")
                                try:
                                    trafo_results = run_async_search(
                                        st.session_state.tools_interface.execute_custom_query,
                                        query=f"""
                                        SELECT t.id, t.desc, t.ord_nr
                                        FROM trafos t
                                        WHERE t.mic_id = {module.mic_id}
                                        ORDER BY t.ord_nr
                                        """
                                    )
                                    
                                    if trafo_results.results:
                                        # Create a dataframe for transformations
                                        trafo_data = []
                                        for trafo in trafo_results.results:
                                            trafo_data.append({
                                                "Order": trafo['ord_nr'],
                                                "ID": trafo['id'],
                                                "Description": trafo['desc']
                                            })
                                        
                                        if trafo_data:
                                            trafo_df = pd.DataFrame(trafo_data)
                                            st.dataframe(trafo_df, use_container_width=True)
                                        else:
                                            st.write("No transformations found for this module.")
                                    else:
                                        st.write("No transformations found for this module.")
                                except Exception as e:
                                    st.warning(f"Could not load transformations for module {module.modins}: {str(e)}")
                    
                    # Remove extra buttons, only keep the Close Details button
                    if st.button("Close Details", key="close_workflow_details"):
                        # Clean up flow state when closing details
                        flow_key = f"workflow_flow_{workflow.id}"
                        if flow_key in st.session_state:
                            del st.session_state[flow_key]
                            
                        st.session_state.workflow_details_view_active = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Error creating flow diagram: {str(e)}")
                    # Print complete traceback for debugging
                    import traceback
                    st.code(traceback.format_exc())
                    
                    # Fallback to a simple representation
                    st.write("#### Module Calls and Transformations")
                    
                    for module_call in workflow.module_calls:
                        module_name = module_call.modins
                        st.write(f"**Module:** {module_name}")
                        
                        # Get transformations for this module
                        try:
                            trafo_results = run_async_search(
                                st.session_state.tools_interface.execute_custom_query,
                                query=f"""
                                SELECT t.id, t.desc, t.ord_nr
                                FROM trafos t
                                WHERE t.mic_id = {module_call.mic_id}
                                ORDER BY t.ord_nr
                                """
                            )
                            
                            if trafo_results.results:
                                # Create a dataframe for transformations
                                trafo_data = []
                                for trafo in trafo_results.results:
                                    trafo_data.append({
                                        "Order": trafo['ord_nr'],
                                        "ID": trafo['id'],
                                        "Description": trafo['desc']
                                    })
                                
                                trafo_df = pd.DataFrame(trafo_data)
                                st.dataframe(trafo_df, use_container_width=True)
                            else:
                                st.write("No transformations found for this module.")
                                
                        except Exception as e:
                            st.warning(f"Could not load transformations for module {module_name}: {str(e)}")
            
            except Exception as e:
                st.error(f"Error loading workflow details: {str(e)}")

with tab2:
    st.header("Search Time Series")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        parameter_id = st.text_input("Parameter ID", key="parameter_id",
                                     help="Enter a parameter ID, e.g., 'H.m'")
    
    with col2:
        qualifier_pattern = st.text_input("Qualifier Pattern", key="qualifier_pattern",
                                        help="Enter a qualifier pattern, e.g., 'observed'")
    
    with col3:
        module_instance = st.text_input("Module Instance", key="module_instance",
                                       help="Enter a module instance name, e.g., 'ImportModule'")
    
    search_button = st.button("Search Time Series", key="search_timeseries_button", use_container_width=True)
    
    if search_button:
        if parameter_id or qualifier_pattern or module_instance:
            with st.spinner("Searching time series..."):
                try:
                    results = run_async_search(
                        st.session_state.tools_interface.search_timeseries,
                        parameter_id=parameter_id,
                        qualifier_pattern=qualifier_pattern,
                        module_instance=module_instance
                    )
                    # Store the search results in session state
                    st.session_state.timeseries_search_results = results
                    display_timeseries_results(results)
                except Exception as e:
                    st.error(f"Error searching time series: {str(e)}")
        else:
            st.warning("Please enter at least one search criterion.")
    # Display stored results if they exist
    elif "timeseries_search_results" in st.session_state:
        display_timeseries_results(st.session_state.timeseries_search_results)
    
    # Display time series details if requested
    if "timeseries_details_view_active" in st.session_state and st.session_state.timeseries_details_view_active:
        st.subheader(f"Time Series Details for ID: {st.session_state.selected_timeseries_id}")
        
        include_transformations = st.checkbox("Include related transformations", value=True,
                                            help="Show transformations that use this time series")
        
        with st.spinner("Loading time series details..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.describe_timeseries,
                    timeseries_id=st.session_state.selected_timeseries_id,
                    include_transformations=include_transformations
                )
                st.markdown(details.markdown_content)
                
                # Button to visualize dependencies
                if st.button("Visualize Time Series", key="visualize_timeseries"):
                    with st.spinner("Generating time series visualization..."):
                        graph = run_async_search(
                            st.session_state.tools_interface.visualize_graph,
                            root_entity_id=st.session_state.selected_timeseries_id,
                            root_entity_type="timeseries",
                            max_depth=3,
                            max_nodes=50,
                            include_properties=True,
                            direction="LR"
                        )
                        
                        # Extract and enhance the mermaid diagram if it exists
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', graph.markdown_content, re.DOTALL)
                        if mermaid_match:
                            mermaid_code = mermaid_match.group(1)
                            enhanced_code = enhance_mermaid_diagram(mermaid_code)
                            # Estimate appropriate height
                            height = estimate_diagram_height(enhanced_code)
                            render_mermaid(enhanced_code, height=height)
                        else:
                            st.markdown(graph.markdown_content)
                
                # Button to analyze dependencies
                if st.button("Analyze Dependencies", key="analyze_timeseries_deps"):
                    with st.spinner("Analyzing time series dependencies..."):
                        deps = run_async_search(
                            st.session_state.tools_interface.analyze_dependencies,
                            entity_id=st.session_state.selected_timeseries_id,
                            entity_type="timeseries"
                        )
                        
                        # Extract and enhance the mermaid diagram if it exists
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', deps.markdown_content, re.DOTALL)
                        if mermaid_match:
                            # Display text content before the diagram
                            content_before = deps.markdown_content.split('```mermaid')[0]
                            if content_before.strip():
                                st.markdown(content_before)
                            
                            mermaid_code = mermaid_match.group(1)
                            enhanced_code = enhance_mermaid_diagram(mermaid_code)
                            # Estimate appropriate height
                            height = estimate_diagram_height(enhanced_code)
                            render_mermaid(enhanced_code, height=height)
                            
                            # Display any text content after the diagram
                            content_after = deps.markdown_content.split('```')[2]
                            if content_after.strip():
                                st.markdown(content_after)
                        else:
                            st.markdown(deps.markdown_content)
                
                # Button to close details
                if st.button("Close Details", key="close_timeseries_details"):
                    st.session_state.timeseries_details_view_active = False
                    st.rerun()
            except Exception as e:
                st.error(f"Error loading time series details: {str(e)}")

    # Add a clear button for time series search
    if "timeseries_search_results" in st.session_state:
        if st.button("Clear Results", key="clear_timeseries_results"):
            del st.session_state.timeseries_search_results
            st.rerun()

with tab3:
    st.header("Search Transformations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        transformation_desc = st.text_input("Transformation Description", key="transformation_desc",
                                          help="Enter a description pattern, e.g., 'interpolation'")
    
    col1, col2 = st.columns(2)
    
    with col1:
        workflow_name_filter = st.text_input("Workflow Name (Optional)", key="workflow_name_filter",
                                           help="Filter by workflow name")
    
    with col2:
        module_config_filter = st.text_input("Module Config (Optional)", key="module_config_filter",
                                           help="Filter by module configuration")
    
    search_button = st.button("Search Transformations", key="search_transformation_button", use_container_width=True)
    
    if search_button:
        if transformation_desc:
            with st.spinner("Searching transformations..."):
                try:
                    results = run_async_search(
                        st.session_state.tools_interface.search_transformations,
                        description_pattern=transformation_desc,
                        workflow_name=workflow_name_filter if workflow_name_filter else None,
                        module_config=module_config_filter if module_config_filter else None
                    )
                    # Store the search results in session state
                    st.session_state.transformation_search_results = results
                    display_transformation_results(results)
                except Exception as e:
                    st.error(f"Error searching transformations: {str(e)}")
        else:
            st.warning("Please enter a transformation description.")
    # Display stored results if they exist
    elif "transformation_search_results" in st.session_state:
        display_transformation_results(st.session_state.transformation_search_results)
    
    # Display transformation details if requested
    if "transformation_details_view_active" in st.session_state and st.session_state.transformation_details_view_active:
        with st.spinner("Loading transformation details..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.get_transformation_details,
                    transformation_id=st.session_state.selected_transformation_id
                )
                
                # Instead of displaying raw markdown, create a more beautiful layout
                if details and details.results:
                    trafo = details.results[0]
                    
                    # Use subheader instead of header to match "View Transformation Details" size
                    st.subheader(f"Transformation {trafo.id}: {trafo.desc}")
                    
                    # Display basic information in a clean expander
                    with st.expander("Basic Information", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Module Instance", trafo.modins)
                            st.metric("Order Number", trafo.ord_nr)
                        with col2:
                            st.metric("Module Config ID", trafo.mic_id)
                            # Add link to view this module in the workflow
                            if st.button("View in Workflow"):
                                # Get the workflow ID from the API
                                workflow_query = run_async_search(
                                    st.session_state.tools_interface.execute_custom_query,
                                    query=f"""
                                    SELECT cs.id FROM call_stacks cs
                                    JOIN mics m ON cs.id = m.cs_id
                                    WHERE m.id = {trafo.mic_id}
                                    LIMIT 1
                                    """
                                )
                                if workflow_query.results:
                                    workflow_id = workflow_query.results[0]["id"]
                                    st.session_state.selected_workflow_id = workflow_id
                                    st.session_state.workflow_details_view_active = True
                                    st.rerun()
                    
                    # Move Transformation Flow up here, right after basic information
                    # Display transformation flow visualization if available
                    visualize_section = [line for line in details.markdown_content.split('\n') if "Transformation Flow" in line]
                    if visualize_section:
                        st.write("**Transformation Flow**")
                        # Extract and display the mermaid diagram if it exists
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', details.markdown_content, re.DOTALL)
                        if mermaid_match:
                            # Use our custom mermaid renderer instead of st.markdown
                            mermaid_code = mermaid_match.group(1)
                            # Estimate appropriate height
                            height = estimate_diagram_height(mermaid_code)
                            render_mermaid(mermaid_code, height=height)
                        else:
                            st.info("No flow diagram available for this transformation.")
                    
                    # Display time series connections with better formatting
                    st.write("**Time Series Connections**")
                    
                    # Display the input and output time series in tabs for better organization
                    input_ts = [ts for ts in trafo.time_series_links if ts.inout == "in"]
                    output_ts = [ts for ts in trafo.time_series_links if ts.inout == "out"]
                    
                    in_tab, out_tab = st.tabs(["Input Time Series", "Output Time Series"])
                    
                    with in_tab:
                        if input_ts:
                            # Create a DataFrame for better display
                            input_data = []
                            for ts in input_ts:
                                # Get the time series details
                                ts_details = run_async_search(
                                    st.session_state.tools_interface.execute_custom_query,
                                    query=f"""
                                    SELECT tss.id, tss.modins, tss.parid, tss.qualifiers 
                                    FROM ts_sets tss
                                    WHERE tss.id = {ts.tss_id}
                                    """
                                )
                                if ts_details.results:
                                    ts_info = ts_details.results[0]
                                    input_data.append({
                                        "ID": ts_info["id"],
                                        "Module": ts_info["modins"],
                                        "Parameter": ts_info["parid"],
                                        "Qualifiers": ts_info["qualifiers"] or "-"
                                    })
                            
                            if input_data:
                                st.dataframe(pd.DataFrame(input_data), use_container_width=True)
                                
                                # Add button to view any input time series
                                if len(input_data) > 0:
                                    if st.button("View Input Time Series Details"):
                                        st.session_state.selected_timeseries_id = input_data[0]["ID"]
                                        st.session_state.timeseries_details_view_active = True
                                        st.rerun()
                        else:
                            st.info("This transformation doesn't have any input time series. This could be because it's a generation/creation transformation that produces new data without inputs, or inputs are defined through other mechanisms like fixed parameters or database queries.")
                    
                    with out_tab:
                        if output_ts:
                            # Create a DataFrame for better display
                            output_data = []
                            for ts in output_ts:
                                # Get the time series details
                                ts_details = run_async_search(
                                    st.session_state.tools_interface.execute_custom_query,
                                    query=f"""
                                    SELECT tss.id, tss.modins, tss.parid, tss.qualifiers 
                                    FROM ts_sets tss
                                    WHERE tss.id = {ts.tss_id}
                                    """
                                )
                                if ts_details.results:
                                    ts_info = ts_details.results[0]
                                    output_data.append({
                                        "ID": ts_info["id"],
                                        "Module": ts_info["modins"],
                                        "Parameter": ts_info["parid"],
                                        "Qualifiers": ts_info["qualifiers"] or "-"
                                    })
                            
                            if output_data:
                                st.dataframe(pd.DataFrame(output_data), use_container_width=True)
                                
                                # Add button to view any output time series
                                if len(output_data) > 0:
                                    if st.button("View Output Time Series Details"):
                                        st.session_state.selected_timeseries_id = output_data[0]["ID"]
                                        st.session_state.timeseries_details_view_active = True
                                        st.rerun()
                        else:
                            st.info("This transformation doesn't have any output time series. This is unusual but could happen for transformations that perform operations but don't produce time series outputs (e.g., database updates, file exports).")
                    
                    # Add buttons for additional actions
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Button to visualize dependencies
                        if st.button("Visualize Transformation", key="visualize_transformation"):
                            with st.spinner("Generating transformation visualization..."):
                                # First get detailed information about the transformation
                                t_details = run_async_search(
                                    st.session_state.tools_interface.get_transformation_details,
                                    transformation_id=st.session_state.selected_transformation_id
                                )
                                
                                # Then create the visualization with additional parameters
                                graph = run_async_search(
                                    st.session_state.tools_interface.visualize_graph,
                                    root_entity_id=st.session_state.selected_transformation_id,
                                    root_entity_type="transformation",
                                    max_depth=3,
                                    max_nodes=50,
                                    include_properties=True,
                                    direction="LR"
                                )
                                # Extract the mermaid diagram
                                mermaid_match = re.search(r'```mermaid\n(.*?)```', graph.markdown_content, re.DOTALL)
                                if mermaid_match:
                                    mermaid_code = mermaid_match.group(1)
                                    
                                    # Enhance and render the diagram in one step
                                    enhanced_code = enhance_mermaid_diagram(mermaid_code, t_details)
                                    height = estimate_diagram_height(enhanced_code)
                                    render_mermaid(enhanced_code, height=height)
                                else:
                                    st.markdown(graph.markdown_content)
                    
                    with col2:
                        # Button to analyze dependencies
                        if st.button("Analyze Dependencies", key="analyze_transformation_deps"):
                            with st.spinner("Analyzing transformation dependencies..."):
                                deps = run_async_search(
                                    st.session_state.tools_interface.analyze_dependencies,
                                    entity_id=st.session_state.selected_transformation_id,
                                    entity_type="transformation"
                                )
                                # Extract and render the mermaid diagram if it exists
                                mermaid_match = re.search(r'```mermaid\n(.*?)```', deps.markdown_content, re.DOTALL)
                                if mermaid_match:
                                    # Display text content before the diagram
                                    content_before = deps.markdown_content.split('```mermaid')[0]
                                    if content_before.strip():
                                        st.markdown(content_before)
                                    
                                    mermaid_code = mermaid_match.group(1)
                                    # Use the enhanced mermaid diagram function
                                    enhanced_code = enhance_mermaid_diagram(mermaid_code)
                                    # Estimate appropriate height
                                    height = estimate_diagram_height(enhanced_code)
                                    render_mermaid(enhanced_code, height=height)
                                    
                                    # Display any text content after the diagram
                                    content_after = deps.markdown_content.split('```')[2]
                                    if content_after.strip():
                                        st.markdown(content_after)
                                else:
                                    st.markdown(deps.markdown_content)
                    
                    with col3:
                        # Button to close details
                        if st.button("Close Details", key="close_transformation_details"):
                            st.session_state.transformation_details_view_active = False
                            st.rerun()
                else:
                    st.error("No details available for this transformation.")
            except Exception as e:
                st.error(f"Error loading transformation details: {str(e)}")

    # Add a clear button for transformation search
    if "transformation_search_results" in st.session_state:
        if st.button("Clear Results", key="clear_transformation_results"):
            del st.session_state.transformation_search_results
            st.rerun()

# Render footer
render_footer() 