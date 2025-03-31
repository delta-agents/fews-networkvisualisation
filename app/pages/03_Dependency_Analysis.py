"""
Afhankelijkheidsanalyse pagina voor FEWS Netwerkvisualisatie.

Deze pagina biedt tools voor het analyseren van afhankelijkheden tussen verschillende entiteiten
in de FEWS-configuratie.
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
    page_title="Afhankelijkheidsanalyse - FEWS Netwerkvisualisatie",
    page_icon="🔗",
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
sidebar_container = render_sidebar(page_title="Afhankelijkheidsanalyse")

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

# Main content
st.title("Afhankelijkheidsanalyse")

# Check if tools interface is available
if "tools_interface" not in st.session_state:
    st.error("Database verbinding niet beschikbaar. Controleer uw configuratie.")
    render_footer()
    st.stop()

st.markdown("""
Analyseer afhankelijkheden tussen entiteiten in uw FEWS-configuratie.
U kunt upstream en downstream relaties analyseren voor:

- **Tijdreeksen**: Ontdek welke transformaties een tijdreeks produceren of gebruiken
- **Transformaties**: Identificeer invoer- en uitvoertijdreeksen voor een transformatie
- **Workflows**: Ontdek welke workflows een workflow aanroepen of door een workflow worden aangeroepen
""")

# Create tabs for different analysis modes
tab1, tab2 = st.tabs(["Basis Afhankelijkheidsanalyse", "Geavanceerde Grafiekvisualisatie"])

with tab1:
    st.header("Basis Afhankelijkheidsanalyse")
    
    st.markdown("""
    Analyseer de afhankelijkheden voor een specifieke entiteit in de FEWS-configuratie.
    Selecteer het entiteitstype en ID om te zien waarvan het afhankelijk is en wat ervan afhankelijk is.
    """)
    
    # Entity type
    entity_type = st.selectbox(
        "Selecteer Entiteitstype", 
        ["timeseries", "transformation", "workflow"],
        key="entity_type"
    )
    
    # Add an expander for finding specific IDs
    with st.expander("Zoek ID via Zoekopdracht"):
        search_help = """
        Gebruik de zoekopdracht hieronder om het ID te vinden van de entiteit die u wilt analyseren.
        U kunt zoeken op naam, beschrijving, parameter of andere relevante attributen.
        """
        st.markdown(search_help)
        
        # Call appropriate search function based on selected entity type
        if entity_type == "timeseries":
            # Time series search
            col1, col2, col3 = st.columns(3)
            with col1:
                param_search = st.text_input("Parameter ID", key="ts_param")
            with col2:
                qual_search = st.text_input("Kwalificatie Patroon", key="ts_qual")
            with col3:
                mod_search = st.text_input("Module Instantie", key="ts_mod")
            
            if st.button("Zoeken", key="ts_button"):
                if param_search or qual_search or mod_search:
                    with st.spinner("Tijdreeksen zoeken..."):
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
                                        "Kwalificatie": ts.qualifiers,
                                        "Module": ts.modins
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("Geen tijdreeksen gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer ten minste één zoekterm in.")
        
        # Similar search options for transformations and workflows
        elif entity_type == "transformation":
            # Transformation search
            col1, col2 = st.columns(2)
            with col1:
                desc_search = st.text_input("Beschrijving", key="trafo_desc")
            with col2:
                mod_search = st.text_input("Module (Optioneel)", key="trafo_mod")
            
            if st.button("Zoeken", key="trafo_button"):
                if desc_search:
                    with st.spinner("Transformaties zoeken..."):
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
                                        "Beschrijving": trafo.desc,
                                        "Module": trafo.modins,
                                        "Workflow": trafo.workflow_name
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("Geen transformaties gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer een beschrijving in.")
        
        else:  # workflow
            # Workflow search
            name_search = st.text_input("Workflow Naam/Beschrijving", key="wf_name")
            
            if st.button("Zoeken", key="wf_button"):
                if name_search:
                    with st.spinner("Workflows zoeken..."):
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
                                        "Beschrijving": wf.desc
                                    })
                                st.session_state.search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.search_results)
                            else:
                                st.info("Geen workflows gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer een zoekterm in.")
    
    # Entity ID input
    entity_id = st.number_input(
        "Tijdreeks ID" if entity_type == "timeseries" else 
        "Transformatie ID" if entity_type == "transformation" else 
        "Workflow ID", 
        min_value=1, value=1, step=1
    )
    
    # Analysis options
    st.subheader("Analyse Opties")
    
    include_graph = st.checkbox("Inclusief grafiekvisualisatie", value=True, 
                              help="Genereer een grafische visualisatie van afhankelijkheden")
    
    # Analyze button
    if st.button("Analyseer Afhankelijkheden", use_container_width=True):
        with st.spinner(f"Afhankelijkheden analyseren voor {entity_type} met ID {entity_id}..."):
            try:
                # Get dependencies
                dependencies = run_async_function(
                    st.session_state.tools_interface.analyze_dependencies,
                    entity_id=entity_id,
                    entity_type=entity_type
                )
                
                # Display results
                st.subheader("Resultaten Afhankelijkheidsanalyse")
                st.markdown(dependencies.markdown_content)
                
                # Generate graph if requested
                if include_graph:
                    with st.spinner("Grafiekvisualisatie genereren..."):
                        graph = run_async_function(
                            st.session_state.tools_interface.visualize_graph,
                            root_entity_id=entity_id,
                            root_entity_type=entity_type,
                            max_depth=2,
                            max_nodes=30,
                            include_properties=True,
                            direction="LR"
                        )
                        
                        st.subheader("Grafiekvisualisatie")
                        st.markdown(graph.markdown_content)
                        
                        # Options to customize the graph
                        st.subheader("Grafiek Aanpassen")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            max_depth = st.slider("Max Diepte", min_value=1, max_value=5, value=2)
                        
                        with col2:
                            max_nodes = st.slider("Max Nodes", min_value=10, max_value=100, value=30)
                        
                        with col3:
                            direction = st.selectbox(
                                "Richting",
                                options=["LR", "RL", "TB", "BT"],
                                index=0,
                                format_func=lambda x: {
                                    "LR": "Links naar Rechts",
                                    "RL": "Rechts naar Links",
                                    "TB": "Boven naar Beneden",
                                    "BT": "Beneden naar Boven"
                                }[x],
                                key="direction_select"
                            )
                        
                        # Button to regenerate graph with new settings
                        if st.button("Grafiek Opnieuw Genereren"):
                            with st.spinner("Bijgewerkte grafiek genereren..."):
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
                st.error(f"Fout bij analyseren van afhankelijkheden: {str(e)}")

with tab2:
    st.header("Aangepaste Grafiek Bouwer")
    
    st.markdown("""
    Bouw een aangepaste grafiekvisualisatie startend vanaf elke entiteit in de FEWS-configuratie.
    U kunt de visualisatie aanpassen om het gewenste detailniveau en bereik te tonen.
    """)
    
    # Entity type
    graph_entity_type = st.selectbox(
        "Selecteer Entiteitstype", 
        ["timeseries", "transformation", "workflow"],
        key="graph_entity_type"
    )
    
    # Search for specific IDs
    with st.expander("Zoek ID via Zoekopdracht"):
        search_help = """
        Gebruik de zoekopdracht hieronder om het ID te vinden van de entiteit waarvanaf u uw grafiek wilt starten.
        U kunt zoeken op naam, beschrijving, parameter of andere relevante attributen.
        """
        st.markdown(search_help)
        
        # Call appropriate search function based on selected entity type
        if graph_entity_type == "timeseries":
            # Time series search
            col1, col2, col3 = st.columns(3)
            with col1:
                param_graph_search = st.text_input("Parameter", key="graph_ts_param")
            with col2:
                qual_graph_search = st.text_input("Kwalificatie", key="graph_ts_qual")
            with col3:
                mod_graph_search = st.text_input("Module", key="graph_ts_mod")
                
            if st.button("Zoeken", key="graph_ts_button"):
                if param_graph_search or qual_graph_search or mod_graph_search:
                    with st.spinner("Tijdreeksen zoeken..."):
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
                                        "Kwalificatie": ts.qualifiers,
                                        "Module": ts.modins
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("Geen tijdreeksen gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer ten minste één zoekterm in.")
        
        # Similar search options for transformations and workflows
        elif graph_entity_type == "transformation":
            # Transformation search
            col1, col2 = st.columns(2)
            with col1:
                desc_graph_search = st.text_input("Beschrijving", key="graph_trafo_desc")
            with col2:
                mod_graph_search = st.text_input("Module (Optioneel)", key="graph_trafo_mod")
                
            if st.button("Zoeken", key="graph_trafo_button"):
                if desc_graph_search:
                    with st.spinner("Transformaties zoeken..."):
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
                                        "Beschrijving": trafo.desc,
                                        "Module": trafo.modins,
                                        "Workflow": trafo.workflow_name
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("Geen transformaties gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer een beschrijving in.")
        
        else:  # workflow
            # Workflow search
            name_graph_search = st.text_input("Workflow Naam/Beschrijving", key="graph_wf_name")
                
            if st.button("Zoeken", key="graph_wf_button"):
                if name_graph_search:
                    with st.spinner("Workflows zoeken..."):
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
                                        "Beschrijving": wf.desc
                                    })
                                st.session_state.graph_search_results = pd.DataFrame(data)
                                st.dataframe(st.session_state.graph_search_results)
                            else:
                                st.info("Geen workflows gevonden die voldoen aan de criteria.")
                        except Exception as e:
                            st.error(f"Fout bij zoeken: {str(e)}")
                else:
                    st.warning("Voer een zoekterm in.")
    
    # Entity ID input for graph visualization - use session state if available
    custom_entity_id = st.number_input(
        "Tijdreeks ID" if graph_entity_type == "timeseries" else 
        "Transformatie ID" if graph_entity_type == "transformation" else 
        "Workflow ID", 
        min_value=1, value=1, step=1, key="custom_entity_id"
    )
    
    # Visualization parameters
    st.subheader("Visualisatie Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        custom_max_depth = st.slider("Max Diepte", min_value=1, max_value=5, value=3, 
                                   help="Maximaal aantal relatieniveaus om weer te geven", key="custom_max_depth")
    
    with col2:
        custom_max_nodes = st.slider("Max Nodes", min_value=10, max_value=100, value=50, 
                                    help="Maximaal aantal nodes om in de grafiek op te nemen", key="custom_max_nodes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        custom_direction = st.selectbox(
            "Grafiek Richting",
            options=["LR", "RL", "TB", "BT"],
            index=0,
            format_func=lambda x: {
                "LR": "Links naar Rechts",
                "RL": "Rechts naar Links",
                "TB": "Boven naar Beneden",
                "BT": "Beneden naar Boven"
            }[x],
            help="Richting waarin de grafiek moet stromen",
            key="custom_direction"
        )
    
    with col2:
        include_properties = st.checkbox("Inclusief Eigenschappen", value=True, 
                                       help="Toon aanvullende eigenschappen voor elke node", key="include_properties")
    
    # Generate custom graph
    if st.button("Genereer Aangepaste Grafiek", use_container_width=True):
        with st.spinner("Aangepaste grafiekvisualisatie genereren..."):
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
                st.subheader("Aangepaste Grafiekvisualisatie")
                st.markdown(graph.markdown_content)
                
                # Option to save graph parameters
                if st.button("Sla Deze Configuratie Op"):
                    if "saved_graph_configs" not in st.session_state:
                        st.session_state.saved_graph_configs = []
                    
                    config_name = st.text_input("Configuratie Naam", value=f"{graph_entity_type}_{custom_entity_id}")
                    
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
                        st.success(f"Configuratie '{config_name}' opgeslagen!")
            except Exception as e:
                st.error(f"Fout bij genereren van aangepaste grafiekvisualisatie: {str(e)}")
    
    # Show saved configurations
    if "saved_graph_configs" in st.session_state and st.session_state.saved_graph_configs:
        st.subheader("Opgeslagen Grafiek Configuraties")
        
        for idx, config in enumerate(st.session_state.saved_graph_configs):
            st.markdown(f"**{config['name']}**: {config['entity_type']} (ID: {config['entity_id']})")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Laden", key=f"load_{idx}"):
                    # Load the configuration
                    st.session_state.graph_entity_type = config["entity_type"]
                    st.session_state.custom_entity_id = config["entity_id"]
                    st.session_state.custom_max_depth = config["max_depth"]
                    st.session_state.custom_max_nodes = config["max_nodes"]
                    st.session_state.custom_direction = config["direction"]
                    st.session_state.include_properties = config["include_properties"]
                    st.experimental_rerun()
            
            with col2:
                if st.button(f"Verwijderen", key=f"delete_{idx}"):
                    # Remove the configuration
                    st.session_state.saved_graph_configs.pop(idx)
                    st.experimental_rerun()

# Render footer
render_footer() 