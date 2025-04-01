"""
Gezondheidscontrole pagina voor FEWS Netwerkvisualisatie.

Deze pagina biedt tools voor het identificeren van problemen en optimalisatiemogelijkheden
in de FEWS-configuratie.
"""
import streamlit as st
import asyncio
import pandas as pd
from pathlib import Path
import sys
import altair as alt

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import application components
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar

# Set page configuration
st.set_page_config(
    page_title="Gezondheidscontrole - FEWS Netwerkvisualisatie",
    page_icon="🔬",
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
sidebar_container = render_sidebar(page_title="Gezondheidscontrole")

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

# Main content
st.title("Gezondheidscontrole & Optimalisatie")

# Check if tools interface is available
if "tools_interface" not in st.session_state:
    st.error("Database verbinding niet beschikbaar. Controleer uw configuratie.")
    render_footer()
    st.stop()

st.markdown("""
Identificeer problemen en optimalisatiemogelijkheden in uw FEWS-configuratie.

Deze pagina helpt u bij:
- Het vinden van "dode punten" (tijdreeksen die worden gegenereerd maar nooit gebruikt)
- Het analyseren van ongebruikelijke patronen in de configuratie
- Het identificeren van potentiële efficiëntieverbeteringen
- Het exporteren van analyseresultaten voor verdere verwerking
""")

# Create tabs for different health checks
tab1, tab2, tab3 = st.tabs(["Dode Punten Analyse", "Configuratie Statistieken", "Aangepaste Controles"])

with tab1:
    st.header("Dode Punten Analyse")
    
    st.markdown("""
    Dode punten zijn tijdreeksen die worden gegenereerd door transformaties maar nooit worden gebruikt als invoer
    voor andere transformaties en niet zijn gemarkeerd als eindpunten. Deze vertegenwoordigen potentiële
    inefficiënties in uw configuratie.
    """)
    
    # Analysis options
    st.subheader("Analyse Opties")
    
    col1, col2 = st.columns(2)
    
    with col1:
        include_producers = st.checkbox("Toon producent informatie", value=True, 
                                      help="Toon welke transformaties elk dood punt produceren")
    
    with col2:
        show_recommendations = st.checkbox("Toon aanbevelingen", value=True,
                                         help="Toon voorgestelde acties om dode punten aan te pakken")
    
    # Add a Run Analysis button
    if st.button("Voer Dode Punten Analyse Uit", use_container_width=True):
        with st.spinner("Dode punten analyseren..."):
            try:
                # Run the dead points analysis
                results = run_async_function(
                    st.session_state.tools_interface.analyze_dead_points,
                    include_producers=include_producers
                )
                
                # Display summary metrics
                st.subheader("Samenvatting")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Dode TimeSeriesSet Punten", results.count)
                
                with col2:
                    st.metric("Betrokken Modules", results.unique_modules)
                
                with col3:
                    st.metric("Betrokken Parameters", results.parameters_affected)
                
                # Display the markdown content first to preserve tool's formatting
                if results.markdown_content:
                    with st.expander("Volledige Analyseresultaten", expanded=False):
                        st.markdown(results.markdown_content)
                
                # Create visualization of modules with dead points using Altair
                if results.module_summary and len(results.module_summary) > 0:
                    st.subheader("Modules met Dode Punten")
                    
                    # Create a DataFrame for the modules
                    module_data = []
                    for module in results.module_summary:
                        module_data.append({
                            "Module": module.module,
                            "Dode Punten": module.count
                        })
                    
                    module_df = pd.DataFrame(module_data)
                    
                    # Create an Altair chart
                    chart = alt.Chart(module_df).mark_bar().encode(
                        x=alt.X('Module:N', sort='-y'),
                        y=alt.Y('Dode Punten:Q', title='Aantal Dode Punten'),
                        color=alt.Color('Dode Punten:Q', scale=alt.Scale(scheme='reds'))
                    ).properties(
                        title='Dode Punten per Module'
                    )
                    
                    st.altair_chart(chart, use_container_width=True)
                
                # Show recommendations if requested
                if show_recommendations and results.recommendations:
                    st.subheader("Aanbevelingen")
                    
                    for i, rec in enumerate(results.recommendations):
                        st.markdown(f"**{i+1}.** {rec}")
                
                # Create a DataFrame for the dead points
                if results.dead_points:
                    dead_points_data = []
                    for dp in results.dead_points:
                        # Convert to dict
                        dp_dict = {
                            "ID": dp.id,
                            "Module": dp.modins,
                            "Parameter": dp.parid,
                            "Kwalificaties": dp.qualifiers,
                            "Type": dp.tstype,
                            "Tijdstap": dp.timess,
                            "Waarde Type": dp.vtype
                        }
                        dead_points_data.append(dp_dict)
                    
                    # Create DataFrame
                    df = pd.DataFrame(dead_points_data)
                    
                    # Add filtering options
                    st.subheader("Filter Dode Punten")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if len(df["Module"].unique()) > 1:
                            module_filter = st.multiselect(
                                "Filter op Module",
                                options=sorted(df["Module"].unique()),
                                default=[]
                            )
                        else:
                            module_filter = []
                    
                    with col2:
                        if len(df["Parameter"].unique()) > 1:
                            param_filter = st.multiselect(
                                "Filter op Parameter",
                                options=sorted(df["Parameter"].unique()),
                                default=[]
                            )
                        else:
                            param_filter = []
                    
                    with col3:
                        if len(df["Type"].unique()) > 1:
                            type_filter = st.multiselect(
                                "Filter op Type",
                                options=sorted(df["Type"].unique()),
                                default=[]
                            )
                        else:
                            type_filter = []
                    
                    # Apply filters
                    filtered_df = df.copy()
                    if module_filter:
                        filtered_df = filtered_df[filtered_df["Module"].isin(module_filter)]
                    if param_filter:
                        filtered_df = filtered_df[filtered_df["Parameter"].isin(param_filter)]
                    if type_filter:
                        filtered_df = filtered_df[filtered_df["Type"].isin(type_filter)]
                    
                    # Show counts
                    st.markdown(f"**Toont {len(filtered_df)} van {len(df)} dode punten**")
                    
                    # Show as table
                    st.subheader("Dode Punten")
                    st.dataframe(filtered_df, use_container_width=True)
                    
                    # Convert to CSV for download
                    csv = filtered_df.to_csv(index=False)
                    
                    # Add download button
                    st.download_button(
                        label="Download Dode Punten CSV",
                        data=csv,
                        file_name="dode_punten.csv",
                        mime="text/csv"
                    )
                    
                    # Distribution analysis with Altair
                    if not filtered_df.empty:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("Module Instanties Die Verwijderd Kunnen Worden")
                            
                            # Use the module_summary from results, which now contains only exclusive dead modules
                            if results.module_summary and len(results.module_summary) > 0:
                                # Create a DataFrame from the exclusive module summary
                                exclusive_modules = [
                                    {"Module Instantie": ms.module, "Aantal Dode Punten": ms.count}
                                    for ms in results.module_summary
                                ]
                                exclusive_modules_df = pd.DataFrame(exclusive_modules)
                                
                                # Display as table
                                st.dataframe(exclusive_modules_df, use_container_width=True)
                            else:
                                st.info("Geen module instanties kunnen veilig worden verwijderd - alle worden gebruikt door actieve tijdreeksen.")
                        
                        with col2:
                            st.subheader("Parameters Die Verwijderd Kunnen Worden")
                            
                            # Get the exclusively_dead_parameters from markdown - a workaround since we don't directly expose this in the model
                            exclusive_parameters = []
                            if "Parameters That Can Be Removed" in results.markdown_content:
                                param_section = results.markdown_content.split("Parameters That Can Be Removed")[1]
                                if "CANNOT REMOVE" not in param_section and "No parameters can be safely removed" not in param_section:
                                    # Parse parameter list from the markdown table rows
                                    param_lines = param_section.split("|-----------|\n")[1].split("\n\n")[0].strip().split("\n")
                                    for line in param_lines:
                                        if line.startswith("| ") and " |" in line:
                                            param = line.strip("| ").split(" |")[0].strip()
                                            if param and "CANNOT REMOVE" not in param:
                                                exclusive_parameters.append(param)
                            
                            if exclusive_parameters:
                                # Create a dataframe with the exclusive parameters
                                exclusive_param_df = pd.DataFrame(exclusive_parameters, columns=["Parameter"])
                                
                                # Display as table
                                st.dataframe(exclusive_param_df, use_container_width=True)
                            else:
                                st.info("Geen parameters kunnen veilig worden verwijderd - alle worden gebruikt door actieve tijdreeksen.")
                        
                        # Add qualifiers section
                        st.subheader("Kwalificaties Die Verwijderd Kunnen Worden")
                        
                        # Get the exclusively_dead_qualifiers from markdown - a workaround since we don't directly expose this in the model
                        exclusive_qualifiers = []
                        if "Qualifiers That Can Be Removed" in results.markdown_content:
                            qual_section = results.markdown_content.split("Qualifiers That Can Be Removed")[1]
                            if "CANNOT REMOVE" not in qual_section and "No qualifiers can be safely removed" not in qual_section:
                                # Parse qualifier list from the markdown table rows
                                qual_lines = qual_section.split("|-----------|\n")[1].split("\n\n")[0].strip().split("\n")
                                for line in qual_lines:
                                    if line.startswith("| ") and " |" in line:
                                        qual = line.strip("| ").split(" |")[0].strip()
                                        if qual and "CANNOT REMOVE" not in qual:
                                            exclusive_qualifiers.append(qual)
                        
                        if exclusive_qualifiers:
                            # Create a dataframe with the exclusive qualifiers
                            exclusive_qual_df = pd.DataFrame(exclusive_qualifiers, columns=["Kwalificatie"])
                            
                            # Display as table
                            st.dataframe(exclusive_qual_df, use_container_width=True)
                        else:
                            st.info("Geen kwalificaties kunnen veilig worden verwijderd - alle worden gebruikt door actieve tijdreeksen.")
                    
                    # Add options to visualize selected dead points
                    st.subheader("Dood Punt Details")

                    # Store the selected ID in session state for stability
                    if "selected_dead_point_id" not in st.session_state:
                        st.session_state.selected_dead_point_id = filtered_df["ID"].iloc[0] if not filtered_df.empty else None

                    # First just display a simple dropdown to select the ID
                    all_options = []
                    for idx, row in filtered_df.iterrows():
                        all_options.append({"id": row["ID"], "label": f"{row['ID']} - {row['Parameter']} ({row['Module']})"})

                    # Create options list for the selectbox
                    id_options = [opt["id"] for opt in all_options]
                    id_labels = [opt["label"] for opt in all_options]

                    # Display dropdown with fixed index
                    if not filtered_df.empty:
                        selected_index = 0
                        if st.session_state.selected_dead_point_id in id_options:
                            selected_index = id_options.index(st.session_state.selected_dead_point_id)
                        
                        selected_option = st.selectbox(
                            "Selecteer een dood punt om details te bekijken",
                            options=range(len(id_options)),
                            format_func=lambda i: id_labels[i],
                            index=selected_index
                        )
                        
                        # Update the session state with the selected ID
                        st.session_state.selected_dead_point_id = id_options[selected_option]
                        
                        # Add a confirmation button to show details
                        if st.button("Toon Dood Punt Details", use_container_width=True):
                            try:
                                selected_dp = st.session_state.selected_dead_point_id
                                st.success(f"Details worden getoond voor tijdreeks ID: {selected_dp}")
                                
                                # Simple query to get time series details
                                basic_query = f"""
                                SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype, ts.timess, ts.vtype
                                FROM ts_sets ts
                                WHERE ts.id = {selected_dp}
                                """
                                
                                details_result = run_async_function(
                                    st.session_state.tools_interface.execute_custom_query,
                                    query=basic_query
                                )
                                
                                if details_result and details_result.results and len(details_result.results) > 0:
                                    # Display in two columns
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        # Display basic details
                                        ts_details = details_result.results[0]
                                        st.write("### Tijdreeks Eigenschappen")
                                        
                                        # Show properties as a markdown table
                                        st.markdown(f"""
                                        | Eigenschap | Waarde |
                                        | --- | --- |
                                        | ID | {ts_details['id']} |
                                        | Module Instantie | {ts_details['modins']} |
                                        | Parameter ID | {ts_details['parid']} |
                                        | Kwalificaties | {ts_details['qualifiers'] or 'Geen'} |
                                        | Type | {ts_details['tstype']} |
                                        | Tijdstap | {ts_details['timess']} |
                                        | Waarde Type | {ts_details['vtype']} |
                                        """)
                                    
                                    with col2:
                                        # Find producer transformations
                                        st.write("### Producerende Transformaties")
                                        
                                        producer_query = f"""
                                        SELECT t.id, t.desc
                                        FROM trafos t
                                        JOIN links l ON t.id = l.trafo_id
                                        WHERE l.tss_id = {selected_dp} AND l.inout = 'out'
                                        LIMIT 10
                                        """
                                        
                                        producers = run_async_function(
                                            st.session_state.tools_interface.execute_custom_query,
                                            query=producer_query
                                        )
                                        
                                        if producers and producers.results and len(producers.results) > 0:
                                            # Build a simple HTML table
                                            html_table = "<table><tr><th>ID</th><th>Beschrijving</th></tr>"
                                            for p in producers.results:
                                                html_table += f"<tr><td>{p['id']}</td><td>{p['desc']}</td></tr>"
                                            html_table += "</table>"
                                            
                                            st.markdown(html_table, unsafe_allow_html=True)
                                        else:
                                            st.info("Geen transformaties gevonden die deze tijdreeks produceren.")
                                    
                                    # Show a simple visualization
                                    st.write("### Eenvoudige Visualisatie")
                                    st.info("Dit is een vereenvoudigde visualisatie die alleen de directe producenten van deze tijdreeks toont.")
                                    
                                    try:
                                        # Use the producers we already queried for a simple visualization
                                        # Build minimal Mermaid code that won't crash
                                        mermaid_code = "graph TD\n"
                                        
                                        # Add the central time series node
                                        ts_label = f"{ts_details['parid']} ({ts_details['modins']})"
                                        mermaid_code += f"    ts[\"🔹 {ts_label}\"]\n"
                                        mermaid_code += "    style ts fill:#f9f,stroke:#333,stroke-width:2px\n"
                                        
                                        # Add producer nodes if we have them
                                        if producers and producers.results:
                                            for idx, p in enumerate(producers.results):
                                                # Clean description for Mermaid
                                                desc = p['desc'].replace('"', "'").replace('[', '(').replace(']', ')')
                                                # Truncate long descriptions
                                                if len(desc) > 30:
                                                    desc = desc[:27] + "..."
                                                
                                                node_id = f"p{idx}"
                                                mermaid_code += f"    {node_id}[\"{desc}\"] --> ts\n"
                                        
                                        # Display the diagram
                                        st.code(mermaid_code, language="mermaid")
                                        
                                    except Exception as e:
                                        st.error(f"Kon geen diagram genereren: {str(e)}")
                                else:
                                    st.error(f"Kon geen details vinden voor tijdreeks ID: {selected_dp}")
                                    
                            except Exception as e:
                                st.error(f"Fout bij ophalen details: {str(e)}")
                    else:
                        st.info("Geen dode punten beschikbaar om te visualiseren met de huidige filters.")
            except Exception as e:
                st.error(f"Fout bij analyseren van dode punten: {str(e)}")

with tab2:
    st.header("Configuratie Statistieken")
    
    st.markdown("""
    Deze tool analyseert uw FEWS-configuratie om statistische inzichten in de structuur te geven,
    waardoor u patronen en potentiële problemen beter kunt begrijpen.
    """)
    
    if st.button("Genereer Configuratie Statistieken", use_container_width=True):
        with st.spinner("Configuratie analyseren..."):
            try:
                # Run queries to get statistics
                modules_query = """
                SELECT modins, COUNT(*) as count
                FROM ts_sets
                GROUP BY modins
                ORDER BY count DESC
                """
                
                parameters_query = """
                SELECT parid, COUNT(*) as count
                FROM ts_sets
                GROUP BY parid
                ORDER BY count DESC
                """
                
                workflows_query = """
                SELECT cs.wf_id, COUNT(mc.id) as module_count
                FROM call_stacks cs
                LEFT JOIN modins_calls mc ON cs.id = mc.call_stack_id
                GROUP BY cs.wf_id
                ORDER BY module_count DESC
                """
                
                # Execute queries
                modules_result = run_async_function(
                    st.session_state.tools_interface.execute_custom_query,
                    query=modules_query
                )
                
                parameters_result = run_async_function(
                    st.session_state.tools_interface.execute_custom_query,
                    query=parameters_query
                )
                
                workflows_result = run_async_function(
                    st.session_state.tools_interface.execute_custom_query,
                    query=workflows_query
                )
                
                # Display statistics
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Module Gebruik")
                    
                    # Create a DataFrame for the modules
                    if modules_result.results:
                        module_df = pd.DataFrame(modules_result.results)
                        
                        # Create an Altair chart
                        module_chart = alt.Chart(module_df.head(10)).mark_bar().encode(
                            x=alt.X('modins:N', sort='-y', title='Module Naam'),
                            y=alt.Y('count:Q', title='Aantal Tijdreeksen'),
                            tooltip=['modins', 'count']
                        ).properties(
                            title='Top 10 Meest Gebruikte Modules'
                        )
                        
                        st.altair_chart(module_chart, use_container_width=True)
                        
                        # Show as table
                        st.dataframe(module_df.head(20), use_container_width=True)
                        
                        # Download option
                        csv = module_df.to_csv(index=False)
                        st.download_button(
                            label="Download Module Statistieken CSV",
                            data=csv,
                            file_name="module_statistieken.csv",
                            mime="text/csv"
                        )
                
                with col2:
                    st.subheader("Parameter Gebruik")
                    
                    # Create a DataFrame for the parameters
                    if parameters_result.results:
                        param_df = pd.DataFrame(parameters_result.results)
                        
                        # Create an Altair chart
                        param_chart = alt.Chart(param_df.head(10)).mark_bar().encode(
                            x=alt.X('parid:N', sort='-y', title='Parameter ID'),
                            y=alt.Y('count:Q', title='Aantal Tijdreeksen'),
                            tooltip=['parid', 'count']
                        ).properties(
                            title='Top 10 Meest Gebruikte Parameters'
                        )
                        
                        st.altair_chart(param_chart, use_container_width=True)
                        
                        # Show as table
                        st.dataframe(param_df.head(20), use_container_width=True)
                        
                        # Download option
                        csv = param_df.to_csv(index=False)
                        st.download_button(
                            label="Download Parameter Statistieken CSV",
                            data=csv,
                            file_name="parameter_statistieken.csv",
                            mime="text/csv"
                        )
                
                # Workflow statistics
                st.subheader("Workflow Statistieken")
                
                if workflows_result.results:
                    workflow_df = pd.DataFrame(workflows_result.results)
                    
                    # Create an Altair chart
                    workflow_chart = alt.Chart(workflow_df.head(10)).mark_bar().encode(
                        x=alt.X('wf_id:N', sort='-y', title='Workflow ID'),
                        y=alt.Y('module_count:Q', title='Aantal Module Configs'),
                        tooltip=['wf_id', 'module_count']
                    ).properties(
                        title='Top 10 Meest Complexe Workflows'
                    )
                    
                    st.altair_chart(workflow_chart, use_container_width=True)
                    
                    # Show as table
                    st.dataframe(workflow_df.head(20), use_container_width=True)
                    
                    # Download option
                    csv = workflow_df.to_csv(index=False)
                    st.download_button(
                        label="Download Workflow Statistieken CSV",
                        data=csv,
                        file_name="workflow_statistieken.csv",
                        mime="text/csv"
                    )
                
                # Overall statistics
                st.subheader("Configuratie Overzicht")
                
                # Get total counts
                counts_query = """
                SELECT 
                    (SELECT COUNT(*) FROM call_stacks) as workflow_count,
                    (SELECT COUNT(*) FROM modins_calls) as module_config_count,
                    (SELECT COUNT(*) FROM ts_sets) as timeseries_count,
                    (SELECT COUNT(*) FROM trafos) as transformation_count,
                    (SELECT COUNT(*) FROM links) as link_count,
                    (SELECT COUNT(*) FROM endpoints) as endpoint_count
                """
                
                counts_result = run_async_function(
                    st.session_state.tools_interface.execute_custom_query,
                    query=counts_query
                )
                
                if counts_result.results:
                    counts = counts_result.results[0]
                    
                    # Create data for Altair chart
                    entity_types = ["Workflows", "Module Configs", "Tijdreeksen", "Transformaties", "Links", "Eindpunten"]
                    entity_counts = [
                        counts["workflow_count"],
                        counts["module_config_count"],
                        counts["timeseries_count"],
                        counts["transformation_count"],
                        counts["link_count"],
                        counts["endpoint_count"]
                    ]
                    
                    fig_data = pd.DataFrame({
                        "Entity Type": entity_types,
                        "Count": entity_counts
                    })
                    
                    # Create chart with Altair
                    entity_chart = alt.Chart(fig_data).mark_bar().encode(
                        x='Entity Type:N',
                        y='Count:Q',
                        color='Entity Type:N',
                        tooltip=['Entity Type', 'Count']
                    ).properties(
                        title='Configuratie Entiteit Aantallen'
                    )
                    
                    st.altair_chart(entity_chart, use_container_width=True)
                    
                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Tijdreeksen per Workflow", 
                                round(counts["timeseries_count"] / counts["workflow_count"], 1) 
                                if counts["workflow_count"] > 0 else 0)
                    
                    with col2:
                        st.metric("Transformaties per Module Config", 
                                round(counts["transformation_count"] / counts["module_config_count"], 1) 
                                if counts["module_config_count"] > 0 else 0)
                    
                    with col3:
                        st.metric("Links per Transformatie", 
                                round(counts["link_count"] / counts["transformation_count"], 1) 
                                if counts["transformation_count"] > 0 else 0)
            except Exception as e:
                st.error(f"Fout bij genereren statistieken: {str(e)}")

with tab3:
    st.header("Aangepaste Controles")
    
    st.markdown("""
    Voer aangepaste SQL-queries uit om specifieke aspecten van uw FEWS-configuratie te analyseren.
    Gebruik deze queries om problemen of potentiële verbeteringen in uw configuratie te identificeren.
    """)
    
    # Predefined queries
    st.subheader("Voorgedefinieerde Controles")
    
    query_options = {
        "Tijdreeksen met Ontbrekende Parameters": """
        SELECT id, modins, parid, qualifiers, tstype
        FROM ts_sets
        WHERE parid = '' OR parid IS NULL
        ORDER BY modins
        """,
        
        "Tijdreeksen met Ontbrekende Kwalificaties": """
        SELECT id, modins, parid, qualifiers, tstype
        FROM ts_sets
        WHERE qualifiers = '' OR qualifiers IS NULL
        ORDER BY modins
        """,
        
        "Ongebruikte Workflows": """
        SELECT cs.id, cs.wf_id, cs.desc
        FROM call_stacks cs
        LEFT JOIN call_stacks child ON child.parent_id = cs.id
        WHERE child.id IS NULL AND cs.parent_id IS NULL
        ORDER BY cs.wf_id
        """,
        
        "Workflows met Meeste Transformaties": """
        SELECT cs.id, cs.wf_id, cs.desc, COUNT(t.id) as transformation_count
        FROM call_stacks cs
        JOIN modins_calls mc ON cs.id = mc.call_stack_id
        JOIN trafos t ON mc.id = t.mic_id
        GROUP BY cs.id
        ORDER BY transformation_count DESC
        LIMIT 20
        """,
        
        "Verweesde Tijdreeksen": """
        SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype
        FROM ts_sets ts
        LEFT JOIN links l ON ts.id = l.tss_id
        WHERE l.tss_id IS NULL
        ORDER BY ts.modins, ts.parid
        """
    }
    
    selected_query = st.selectbox("Selecteer een voorgedefinieerde query", options=list(query_options.keys()))
    
    if st.button("Voer Voorgedefinieerde Query Uit", key="run_predefined"):
        with st.spinner("Query uitvoeren..."):
            try:
                query = query_options[selected_query]
                results = run_async_function(
                    st.session_state.tools_interface.execute_custom_query,
                    query=query
                )
                
                if results and results.results:
                    # Convert results to DataFrame
                    df = pd.DataFrame(results.results)
                    
                    # Display as table
                    st.subheader(f"Resultaten: {selected_query}")
                    st.dataframe(df, use_container_width=True)
                    
                    # Show count
                    st.info(f"{len(df)} records gevonden")
                    
                    # Display markdown content if available
                    if hasattr(results, 'markdown_content') and results.markdown_content:
                        with st.expander("Gedetailleerde Resultaten", expanded=False):
                            st.markdown(results.markdown_content)
                    
                    # Add download option
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Resultaten CSV",
                        data=csv,
                        file_name=f"{selected_query.lower().replace(' ', '_')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Geen resultaten gevonden voor deze query.")
            except Exception as e:
                st.error(f"Fout bij uitvoeren query: {str(e)}")
    
    # Custom query input
    st.subheader("Aangepaste SQL Query")
    
    query = st.text_area(
        "Voer SQL Query in",
        height=150,
        value="""
-- Voorbeeld query: Vind tijdreeksen met specifieke parameter
SELECT id, modins, parid, qualifiers, tstype
FROM ts_sets
WHERE parid LIKE '%H.m%'
LIMIT 20
""",
        help="Voer een SQL-query in om uw FEWS-configuratie te analyseren"
    )
    
    if st.button("Voer Aangepaste Query Uit", key="run_custom"):
        if query:
            with st.spinner("Aangepaste query uitvoeren..."):
                try:
                    # Execute the custom query
                    results = run_async_function(
                        st.session_state.tools_interface.execute_custom_query,
                        query=query
                    )
                    
                    if results and results.results:
                        # Convert results to DataFrame
                        df = pd.DataFrame(results.results)
                        
                        # Display as table
                        st.subheader("Aangepaste Query Resultaten")
                        st.dataframe(df, use_container_width=True)
                        
                        # Show count
                        st.info(f"{len(df)} records gevonden")
                        
                        # Display markdown content if available
                        if hasattr(results, 'markdown_content') and results.markdown_content:
                            with st.expander("Gedetailleerde Resultaten", expanded=False):
                                st.markdown(results.markdown_content)
                        
                        # Add download option
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download Resultaten CSV",
                            data=csv,
                            file_name="aangepaste_query_resultaten.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("Geen resultaten gevonden voor deze query.")
                except Exception as e:
                    st.error(f"Fout bij uitvoeren query: {str(e)}")
        else:
            st.warning("Voer a.u.b. een SQL query in.")

# Render footer
render_footer() 