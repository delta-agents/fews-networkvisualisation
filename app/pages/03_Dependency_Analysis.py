"""
Dependency Analysis page for FEWS Network Visualization.

This page provides tools for analyzing dependencies between different entities
in the FEWS configuration.
"""
import streamlit as st
import asyncio
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar

# Set page configuration
st.set_page_config(
    page_title="Dependency Analysis - FEWS Network Visualization",
    page_icon="🔗",
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
sidebar_container = render_sidebar(page_title="Dependency Analysis")

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

# Main content
st.title("Dependency Analysis")

# Check if tools interface is available
if "tools_interface" not in st.session_state:
    st.error("Database connection not available. Please check your configuration.")
    render_footer()
    st.stop()

st.markdown("""
Analyze dependencies between entities in your FEWS configuration.
You can analyze upstream and downstream relationships for:

- **Time Series**: Find which transformations produce or consume a time series
- **Transformations**: Identify input and output time series for a transformation
- **Workflows**: Discover which workflows call or are called by a workflow
""")

# Create tabs for different analysis modes
tab1, tab2 = st.tabs(["Basic Dependency Analysis", "Advanced Graph Visualization"])

with tab1:
    st.header("Basic Dependency Analysis")
    
    st.markdown("""
    Analyze the dependencies for a specific entity in the FEWS configuration.
    Select the entity type and ID to see what it depends on and what depends on it.
    """)
    
    # Entity type
    entity_type = st.selectbox(
        "Select Entity Type", 
        ["timeseries", "transformation", "workflow"],
        key="entity_type"
    )
    
    # Add an expander for finding specific IDs
    with st.expander("Find ID by Search"):
        search_help = """
        Use the search below to find the ID of the entity you want to analyze.
        You can search by name, description, parameter, or other relevant attributes.
        """
        st.markdown(search_help)
        
        # Call appropriate search function based on selected entity type
        if entity_type == "timeseries":
            # Time series search
            col1, col2, col3 = st.columns(3)
            with col1:
                param_search = st.text_input("Parameter ID", key="ts_param")
            with col2:
                qual_search = st.text_input("Qualifier Pattern", key="ts_qual")
            with col3:
                mod_search = st.text_input("Module Instance", key="ts_mod")
            
            if st.button("Search", key="ts_button"):
                if param_search or qual_search or mod_search:
                    with st.spinner("Searching time series..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_timeseries,
                                parameter_id=param_search,
                                qualifier_pattern=qual_search,
                                module_instance=mod_search
                            )
                            
                            if results.results:
                                # Convert to DataFrame for better display
                                data = []
                                for ts in results.results:
                                    data.append({
                                        "ID": ts.id,
                                        "Parameter": ts.parid,
                                        "Qualifier": ts.qualifiers,
                                        "Module": ts.modins
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("No time series found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter at least one search term.")
        
        # Similar search options for transformations and workflows
        elif entity_type == "transformation":
            # Transformation search
            col1, col2 = st.columns(2)
            with col1:
                desc_search = st.text_input("Description", key="trafo_desc")
            with col2:
                mod_search = st.text_input("Module (Optional)", key="trafo_mod")
            
            if st.button("Search", key="trafo_button"):
                if desc_search:
                    with st.spinner("Searching transformations..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_transformations,
                                description_pattern=desc_search,
                                module_config=mod_search if mod_search else None
                            )
                            
                            if results.results:
                                # Convert to DataFrame for better display
                                data = []
                                for trafo in results.results:
                                    data.append({
                                        "ID": trafo.id,
                                        "Description": trafo.desc,
                                        "Module": trafo.modins,
                                        "Workflow": trafo.workflow_name
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("No transformations found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter a description.")
        
        else:  # workflow
            # Workflow search
            name_search = st.text_input("Workflow Name/Description", key="wf_name")
            
            if st.button("Search", key="wf_button"):
                if name_search:
                    with st.spinner("Searching workflows..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_workflows,
                                name_pattern=name_search
                            )
                            
                            if results.results:
                                # Convert to DataFrame for better display
                                data = []
                                for wf in results.results:
                                    data.append({
                                        "ID": wf.id,
                                        "Workflow": wf.wf_id,
                                        "Description": wf.desc
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("No workflows found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter a search term.")
    
    # Entity ID input
    entity_id = st.number_input(
        "Time Series ID" if entity_type == "timeseries" else 
        "Transformation ID" if entity_type == "transformation" else 
        "Workflow ID", 
        min_value=1, value=1, step=1
    )
    
    # Analysis options
    st.subheader("Analysis Options")
    
    include_graph = st.checkbox("Include graph visualization", value=True, 
                              help="Generate a graph visualization of dependencies")
    
    # Analyze button
    if st.button("Analyze Dependencies", use_container_width=True):
        with st.spinner(f"Analyzing dependencies for {entity_type} with ID {entity_id}..."):
            try:
                # Get dependencies
                dependencies = run_async_function(
                    st.session_state.tools_interface.analyze_dependencies,
                    entity_id=entity_id,
                    entity_type=entity_type
                )
                
                # Display results
                st.subheader("Dependency Analysis Results")
                st.markdown(dependencies.markdown_content)
                
                # Generate graph if requested
                if include_graph:
                    with st.spinner("Generating graph visualization..."):
                        graph = run_async_function(
                            st.session_state.tools_interface.visualize_graph,
                            root_entity_id=entity_id,
                            root_entity_type=entity_type,
                            max_depth=2,
                            max_nodes=30,
                            include_properties=True,
                            direction="LR"
                        )
                        
                        st.subheader("Graph Visualization")
                        st.markdown(graph.markdown_content)
                        
                        # Options to customize the graph
                        st.subheader("Customize Graph")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            max_depth = st.slider("Max Depth", min_value=1, max_value=5, value=2)
                        
                        with col2:
                            max_nodes = st.slider("Max Nodes", min_value=10, max_value=100, value=30)
                        
                        with col3:
                            direction = st.selectbox(
                                "Direction",
                                options=["LR", "RL", "TB", "BT"],
                                index=0,
                                format_func=lambda x: {
                                    "LR": "Left to Right",
                                    "RL": "Right to Left",
                                    "TB": "Top to Bottom",
                                    "BT": "Bottom to Top"
                                }[x],
                                key="direction_select"
                            )
                        
                        # Button to regenerate graph with new settings
                        if st.button("Regenerate Graph"):
                            with st.spinner("Generating updated graph..."):
                                graph = run_async_function(
                                    st.session_state.tools_interface.visualize_graph,
                                    root_entity_id=entity_id,
                                    root_entity_type=entity_type,
                                    max_depth=max_depth,
                                    max_nodes=max_nodes,
                                    include_properties=True,
                                    direction=direction
                                )
                                st.markdown(graph.markdown_content)
            except Exception as e:
                st.error(f"Error analyzing dependencies: {str(e)}")

with tab2:
    st.header("Custom Graph Builder")
    
    st.markdown("""
    Build a custom graph visualization starting from any entity in the FEWS configuration.
    You can customize the visualization to show the desired level of detail and scope.
    """)
    
    # Entity type
    graph_entity_type = st.selectbox(
        "Select Entity Type", 
        ["timeseries", "transformation", "workflow"],
        key="graph_entity_type"
    )
    
    # Search for specific IDs
    with st.expander("Find ID by Search"):
        search_help = """
        Use the search below to find the ID of the entity you want to start your graph from.
        You can search by name, description, parameter, or other relevant attributes.
        """
        st.markdown(search_help)
        
        # Call appropriate search function based on selected entity type
        if graph_entity_type == "timeseries":
            # Time series search
            col1, col2, col3 = st.columns(3)
            with col1:
                param_graph_search = st.text_input("Parameter", key="graph_ts_param")
            with col2:
                qual_graph_search = st.text_input("Qualifier", key="graph_ts_qual")
            with col3:
                mod_graph_search = st.text_input("Module", key="graph_ts_mod")
                
            if st.button("Search", key="graph_ts_button"):
                if param_graph_search or qual_graph_search or mod_graph_search:
                    with st.spinner("Searching time series..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_timeseries,
                                parameter_id=param_graph_search,
                                qualifier_pattern=qual_graph_search,
                                module_instance=mod_graph_search
                            )
                            
                            if results.results:
                                # Convert to DataFrame and store in session state for ID selection
                                data = []
                                for ts in results.results:
                                    data.append({
                                        "ID": ts.id,
                                        "Parameter": ts.parid,
                                        "Qualifier": ts.qualifiers,
                                        "Module": ts.modins
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("No time series found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter at least one search term.")
        
        # Similar search options for transformations and workflows
        elif graph_entity_type == "transformation":
            # Transformation search
            col1, col2 = st.columns(2)
            with col1:
                desc_graph_search = st.text_input("Description", key="graph_trafo_desc")
            with col2:
                mod_graph_search = st.text_input("Module (Optional)", key="graph_trafo_mod")
                
            if st.button("Search", key="graph_trafo_button"):
                if desc_graph_search:
                    with st.spinner("Searching transformations..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_transformations,
                                description_pattern=desc_graph_search,
                                module_config=mod_graph_search if mod_graph_search else None
                            )
                            
                            if results.results:
                                # Convert to DataFrame and store in session state for ID selection
                                data = []
                                for trafo in results.results:
                                    data.append({
                                        "ID": trafo.id,
                                        "Description": trafo.desc,
                                        "Module": trafo.modins,
                                        "Workflow": trafo.workflow_name
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("No transformations found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter a description.")
        
        else:  # workflow
            # Workflow search
            name_graph_search = st.text_input("Workflow Name/Description", key="graph_wf_name")
                
            if st.button("Search", key="graph_wf_button"):
                if name_graph_search:
                    with st.spinner("Searching workflows..."):
                        try:
                            results = run_async_function(
                                st.session_state.tools_interface.search_workflows,
                                name_pattern=name_graph_search
                            )
                            
                            if results.results:
                                # Convert to DataFrame and store in session state for ID selection
                                data = []
                                for wf in results.results:
                                    data.append({
                                        "ID": wf.id,
                                        "Workflow": wf.wf_id,
                                        "Description": wf.desc
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("No workflows found matching the criteria.")
                        except Exception as e:
                            st.error(f"Error searching: {str(e)}")
                else:
                    st.warning("Please enter a search term.")
    
    # Entity ID input for graph visualization - use session state if available
    custom_entity_id = st.number_input(
        "Time Series ID" if graph_entity_type == "timeseries" else 
        "Transformation ID" if graph_entity_type == "transformation" else 
        "Workflow ID", 
        min_value=1, value=1, step=1, key="custom_entity_id"
    )
    
    # Visualization parameters
    st.subheader("Visualization Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        custom_max_depth = st.slider("Max Depth", min_value=1, max_value=5, value=3, 
                                   help="Maximum number of relationship levels to display", key="custom_max_depth")
    
    with col2:
        custom_max_nodes = st.slider("Max Nodes", min_value=10, max_value=100, value=50, 
                                    help="Maximum number of nodes to include in the graph", key="custom_max_nodes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        custom_direction = st.selectbox(
            "Graph Direction",
            options=["LR", "RL", "TB", "BT"],
            index=0,
            format_func=lambda x: {
                "LR": "Left to Right",
                "RL": "Right to Left",
                "TB": "Top to Bottom",
                "BT": "Bottom to Top"
            }[x],
            help="Direction in which the graph should flow",
            key="custom_direction"
        )
    
    with col2:
        include_properties = st.checkbox("Include Properties", value=True, 
                                       help="Show additional properties for each node", key="include_properties")
    
    # Generate custom graph
    if st.button("Generate Custom Graph", use_container_width=True):
        with st.spinner("Generating custom graph visualization..."):
            try:
                # Generate graph visualization
                graph = run_async_function(
                    st.session_state.tools_interface.visualize_graph,
                    root_entity_id=custom_entity_id,
                    root_entity_type=graph_entity_type,
                    max_depth=custom_max_depth,
                    max_nodes=custom_max_nodes,
                    include_properties=include_properties,
                    direction=custom_direction
                )
                
                # Display graph
                st.subheader("Custom Graph Visualization")
                st.markdown(graph.markdown_content)
                
                # Option to save graph parameters
                if st.button("Save This Configuration"):
                    if "saved_graph_configs" not in st.session_state:
                        st.session_state.saved_graph_configs = []
                    
                    config_name = st.text_input("Configuration Name", value=f"{graph_entity_type}_{custom_entity_id}")
                    
                    if config_name:
                        # Save the configuration
                        new_config = {
                            "name": config_name,
                            "entity_type": graph_entity_type,
                            "entity_id": custom_entity_id,
                            "max_depth": custom_max_depth,
                            "max_nodes": custom_max_nodes,
                            "direction": custom_direction,
                            "include_properties": include_properties
                        }
                        
                        st.session_state.saved_graph_configs.append(new_config)
                        st.success(f"Configuration '{config_name}' saved!")
            except Exception as e:
                st.error(f"Error generating custom graph visualization: {str(e)}")
    
    # Show saved configurations
    if "saved_graph_configs" in st.session_state and st.session_state.saved_graph_configs:
        st.subheader("Saved Graph Configurations")
        
        for idx, config in enumerate(st.session_state.saved_graph_configs):
            st.markdown(f"**{config['name']}**: {config['entity_type']} (ID: {config['entity_id']})")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Load", key=f"load_{idx}"):
                    # Load the configuration
                    st.session_state.graph_entity_type = config["entity_type"]
                    st.session_state.custom_entity_id = config["entity_id"]
                    st.session_state.custom_max_depth = config["max_depth"]
                    st.session_state.custom_max_nodes = config["max_nodes"]
                    st.session_state.custom_direction = config["direction"]
                    st.session_state.include_properties = config["include_properties"]
                    st.experimental_rerun()
            
            with col2:
                if st.button(f"Delete", key=f"delete_{idx}"):
                    # Remove the configuration
                    st.session_state.saved_graph_configs.pop(idx)
                    st.experimental_rerun()

# Render footer
render_footer() 