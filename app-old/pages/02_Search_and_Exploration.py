"""
Zoeken en Verkennen pagina voor FEWS Netwerkvisualisatie.

Deze pagina biedt toegang tot zoekfuncties voor workflows, tijdreeksen en transformaties.
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

# Functie om Mermaid-diagrammen weer te geven
def render_mermaid(mermaid_code, height=200):
    """
    Geeft een Mermaid-diagram weer van de gegeven code met behulp van JavaScript.
    
    Args:
        mermaid_code: De Mermaid-diagramcode om weer te geven
        height: Optionele hoogte in pixels (standaard: 200)
    """
    
    # Maak een unieke ID voor dit diagram
    diagram_id = f"mermaid-diagram-{random.randint(1, 100000)}"
    
    # HTML met ingesloten Mermaid JS
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                mermaid.initialize({{ 
                    startOnLoad: true,
                    // Gebruik compactere stijl
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
            /* Maak tekst kleiner in het diagram */
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
    
    # Geef de HTML weer met aangepaste hoogte
    components.v1.html(html, height=height)

# Helperfunctie om diagramhoogte te schatten op basis van complexiteit
def estimate_diagram_height(mermaid_code):
    """
    Schat een geschikte hoogte voor het diagram op basis van de complexiteit.
    
    Args:
        mermaid_code: De Mermaid-diagramcode
        
    Returns:
        Geschatte hoogte in pixels
    """
    # Tel inkomende en uitgaande tijdreeksen verbindingen
    lines = mermaid_code.strip().split('\n')
    
    # Zoek naar randen die verbonden zijn met tijdreeksen
    in_ts_count = 0
    out_ts_count = 0
    
    for line in lines:
        # Controleer op invoertijdreeksen (randen die eindigen bij ts_)
        if re.search(r'\w+\s*-->\s*ts_\d+', line):
            in_ts_count += 1
        # Controleer op uitvoertijdreeksen (randen die beginnen bij ts_)
        if re.search(r'ts_\d+\s*-->', line):
            out_ts_count += 1
    
    # Gebruik het maximum aantal van invoer- of uitvoertijdreeksen
    ts_count = max(in_ts_count, out_ts_count)
    
    # Bereken hoogte op basis van aantal tijdreeksen met lagere waarden
    height_per_ts = 20
    base_height = 15
    
    # Als er geen tijdreeksen gevonden zijn, val terug op nodetelling
    if ts_count == 0:
        node_count = sum(1 for line in lines if re.search(r'\w+(\[.*?\]|\(.*?\)|\>.*?\]|\{.*?\})', line))
        edge_count = sum(1 for line in lines if re.search(r'\w+\s*-->', line))
        height = base_height + (node_count + edge_count) * 10
    else:
        height = base_height + ts_count * height_per_ts
    
    # Zorg voor redelijke grenzen aan de hoogte
    return max(150, min(height, 600))

# Voeg oudermap toe aan pad voor imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Importeer applicatiecomponenten
from app.utils.config import load_config
from app.components.header import render_header
from app.components.footer import render_footer
from app.components.sidebar import render_sidebar

# Stel paginaconfiguratie in
st.set_page_config(
    page_title="Zoeken en Verkennen - FEWS Netwerkvisualisatie",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Laad configuratie
config = load_config()

# Geef header weer
render_header(
    title=config.get("app_title", "FEWS Netwerkvisualisatie"),
    version=config.get("app_version", "0.2.0")
)

# Geef sidebar weer
sidebar_container = render_sidebar(page_title="Zoeken & Verkennen")

def run_async_search(search_function, **kwargs):
    """Voer een asynchrone functie uit en retourneer de resultaten."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(search_function(**kwargs))
    finally:
        loop.close()

def execute_custom_query(query):
    """Voer een aangepaste SQL-query uit met behulp van de tools interface."""
    return st.session_state.tools_interface.execute_custom_query(query=query)

def display_timeseries_results(results):
    """Geef tijdreeks-zoekresultaten weer in een vereenvoudigd formaat."""
    if not results.results:
        st.info("Geen tijdreeksen gevonden die voldoen aan uw criteria.")
        return
        
    # Converteer resultaten naar DataFrame voor betere weergave
    data = []
    for ts in results.results:
        # Haal eindpuntinformatie op
        endpoint_info = ""
        if hasattr(ts, 'endpoint') and ts.endpoint:
            if hasattr(ts, 'endpoint_desc') and ts.endpoint_desc:
                endpoint_info = ts.endpoint_desc
            else:
                endpoint_info = "✓"
        
        data.append({
            "ID": ts.id,
            "Module": ts.modins,
            "Parameter": ts.parid,
            "Kwalificaties": ts.qualifiers,
            "Type": ts.tstype,
            "Tijdstap": ts.timess,
            "Waarde Type": ts.vtype,
            "Eindpunt": endpoint_info
        })
    
    df = pd.DataFrame(data)
    
    # Basis filtering - alleen Parameter filter
    filters = {}
    
    if len(df["Parameter"].unique()) > 1:
        filters["Parameter"] = st.multiselect(
            "Filter op Parameter",
            options=sorted(df["Parameter"].unique()),
            default=[]
        )
    
    # Pas filters toe
    filtered_df = df.copy()
    for column, selected_values in filters.items():
        if selected_values:
            filtered_df = filtered_df[filtered_df[column].isin(selected_values)]
    
    # Sorteren
    sort_column = st.selectbox("Sorteer op", df.columns.tolist(), key="timeseries_sort")
    sort_ascending = st.checkbox("Oplopende volgorde", True, key="timeseries_sort_order")
    filtered_df_sorted = filtered_df.sort_values(by=sort_column, ascending=sort_ascending)
    
    # Toon resultaten
    st.dataframe(filtered_df_sorted, use_container_width=True)
    st.markdown(f"**{len(filtered_df)} tijdreeksen gevonden** (gefilterd van {len(df)} totale resultaten)")
    
    # Download resultaten
    if len(filtered_df) > 0:
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download Resultaten (CSV)",
            data=csv,
            file_name="tijdreeks_resultaten.csv",
            mime="text/csv",
        )
    
    # Selecteer tijdreeks voor details
    st.subheader("Bekijk Tijdreeks Details")
    
    def on_timeseries_select():
        st.session_state.selected_timeseries_id = st.session_state.timeseries_selector
        st.session_state.timeseries_details_view_active = True
        
    st.selectbox(
        "Selecteer een tijdreeks om details te bekijken",
        options=filtered_df["ID"].tolist(),
        format_func=lambda x: f"{x} - {filtered_df.loc[filtered_df['ID'] == x, 'Parameter'].iloc[0]} ({filtered_df.loc[filtered_df['ID'] == x, 'Module'].iloc[0]})",
        key="timeseries_selector",
        on_change=on_timeseries_select
    )

def display_transformation_results(results):
    """Geef transformatie-zoekresultaten weer in een vereenvoudigd formaat."""
    if not results.results:
        st.info("Geen transformaties gevonden die voldoen aan uw criteria.")
        return
        
    # Converteer resultaten naar DataFrame voor betere weergave
    data = []
    for trafo in results.results:
        data.append({
            "Workflow": trafo.workflow_name,
            "Module Config": trafo.modins,
            "Transformatie": trafo.id,
            "Volgorde": trafo.ord_nr,
            "Beschrijving": trafo.desc
        })
    
    df = pd.DataFrame(data)
    
    # Basis filtering
    col1, col2 = st.columns(2)
    filters = {}
    
    with col1:
        if len(df["Module Config"].unique()) > 1:
            filters["Module Config"] = st.multiselect(
                "Filter op Module Config",
                options=sorted(df["Module Config"].unique()),
                default=[]
            )
            
    with col2:
        if len(df["Workflow"].unique()) > 1:
            filters["Workflow"] = st.multiselect(
                "Filter op Workflow",
                options=sorted(df["Workflow"].unique()),
                default=[]
            )
    
    # Pas filters toe
    filtered_df = df.copy()
    for column, selected_values in filters.items():
        if selected_values:
            filtered_df = filtered_df[filtered_df[column].isin(selected_values)]
    
    # Sorteren
    sort_column = st.selectbox("Sorteer op", df.columns.tolist(), key="transformation_sort")
    sort_ascending = st.checkbox("Oplopende volgorde", True, key="transformation_sort_order")
    filtered_df_sorted = filtered_df.sort_values(by=sort_column, ascending=sort_ascending)
    
    # Toon resultaten
    st.dataframe(filtered_df_sorted, use_container_width=True)
    st.markdown(f"**{len(filtered_df)} transformaties gevonden** (gefilterd van {len(df)} totale resultaten)")
    
    # Download optie
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download gefilterde resultaten als CSV",
        data=csv,
        file_name="transformatie_zoekresultaten.csv",
        mime="text/csv"
    )
    
    # Selecteer transformatie voor details
    st.subheader("Bekijk Transformatie Details")
    
    def on_transformation_select():
        st.session_state.selected_transformation_id = st.session_state.transformation_selector
        st.session_state.transformation_details_view_active = True
        
    st.selectbox(
        "Selecteer een transformatie om details te bekijken",
        options=filtered_df["Transformatie"].tolist(),
        format_func=lambda x: f"{x} - {filtered_df.loc[filtered_df['Transformatie'] == x, 'Beschrijving'].iloc[0]}",
        key="transformation_selector",
        on_change=on_transformation_select
    )

# Main content
st.title("Zoeken en Verkennen")

# Check if tools interface is available
if "tools_interface" not in st.session_state:
    st.error("Database verbinding niet beschikbaar. Controleer uw configuratie.")
    render_footer()
    st.stop()

# Helper function to fetch time series options
def get_timeseries_options():
    """Haal alle beschikbare parameter IDs, kwalificaties, module instanties en eindpuntbeschrijvingen op voor tijdreeksfilters"""
    try:
        # Query for parameter IDs
        parameter_query = "SELECT DISTINCT parid FROM ts_sets ORDER BY parid"
        parameter_ids = run_async_search(lambda: execute_custom_query(parameter_query))
        parameter_ids = [row['parid'] for row in parameter_ids.results] if parameter_ids and hasattr(parameter_ids, 'results') else []
        
        # Query for qualifiers
        qualifier_query = """
            SELECT DISTINCT qualifiers 
            FROM ts_sets 
            WHERE qualifiers IS NOT NULL AND qualifiers != '' 
            ORDER BY qualifiers
        """
        qualifiers = run_async_search(lambda: execute_custom_query(qualifier_query))
        qualifiers = [row['qualifiers'] for row in qualifiers.results] if qualifiers and hasattr(qualifiers, 'results') else []
        
        # Query for module instances
        module_query = "SELECT DISTINCT modins FROM ts_sets ORDER BY modins"
        module_instances = run_async_search(lambda: execute_custom_query(module_query))
        module_instances = [row['modins'] for row in module_instances.results] if module_instances and hasattr(module_instances, 'results') else []
        
        # Query for endpoint descriptions - ensure we get non-empty descriptions
        endpoint_query = """
            SELECT DISTINCT e.desc
            FROM endpoints e
            WHERE e.desc IS NOT NULL AND e.desc != ''
            ORDER BY e.desc
        """
        endpoint_results = run_async_search(lambda: execute_custom_query(endpoint_query))
        endpoint_descriptions = []
        if endpoint_results and hasattr(endpoint_results, 'results'):
            for row in endpoint_results.results:
                if row['desc'] and row['desc'].strip() not in endpoint_descriptions:
                    endpoint_descriptions.append(row['desc'].strip())
        
        return {
            "parameter_ids": parameter_ids,
            "qualifiers": qualifiers,
            "module_instances": module_instances,
            "endpoint_descriptions": endpoint_descriptions
        }
    except Exception as e:
        st.error(f"Fout bij ophalen tijdreeksopties: {str(e)}")
        return {"parameter_ids": [], "qualifiers": [], "module_instances": [], "endpoint_descriptions": []}

def filter_timeseries_options(field, selected_parameter=None, selected_qualifier=None, selected_module=None, selected_endpoint=None):
    """Haal gefilterde opties op voor een specifiek veld op basis van andere selecties"""
    # Start met het opbouwen van de query
    base_query = f"SELECT DISTINCT ts.{field} FROM ts_sets ts"
    
    # Voeg eindpunt controle toe als eindpuntfilter is geselecteerd
    if selected_endpoint is not None:
        # Controleer of selected_endpoint een boolean of string is
        if isinstance(selected_endpoint, bool):
            # Boolean geval - filter op eindpunt bestaan
            if selected_endpoint:
                # Toon alleen eindpunten (elk eindpunt)
                base_query += " INNER JOIN endpoints e ON ts.id = e.tss_id"
            else:
                # Toon alleen niet-eindpunten
                base_query += " LEFT JOIN endpoints e ON ts.id = e.tss_id WHERE e.tss_id IS NULL"
        else:
            # String geval - filter op eindpunt beschrijving
            base_query += " INNER JOIN endpoints e ON ts.id = e.tss_id"
    else:
        # Geen eindpuntfilter - nog steeds joinen voor veldselectie indien nodig
        if field == "endpoint_desc":
            base_query += " LEFT JOIN endpoints e ON ts.id = e.tss_id"
    
    # Bouw de WHERE clausule
    conditions = []
    
    # Voeg filtercondities toe op basis van selecties
    if selected_parameter and field != "parid":
        # Escape single quotes in de parameterwaarde door ze te verdubbelen (SQL standaard)
        safe_param = selected_parameter.replace("'", "''") if selected_parameter else ""
        conditions.append(f"ts.parid = '{safe_param}'")
        
    if selected_qualifier and field != "qualifiers":
        # Escape single quotes in de kwalificatiewaarde
        safe_qualifier = selected_qualifier.replace("'", "''") if selected_qualifier else ""
        conditions.append(f"ts.qualifiers = '{safe_qualifier}'")
        
    if selected_module and field != "modins":
        # Escape single quotes in de modulewaarde
        safe_module = selected_module.replace("'", "''") if selected_module else ""
        conditions.append(f"ts.modins = '{safe_module}'")
        
    # Voeg eindpuntbeschrijving conditie toe als geselecteerd en het is een string
    if selected_endpoint is not None and isinstance(selected_endpoint, str):
        # Escape single quotes in de eindpuntbeschrijving
        safe_endpoint = selected_endpoint.replace("'", "''")
        conditions.append(f"e.desc = '{safe_endpoint}'")
    
    # Voeg WHERE clausule toe als er condities zijn
    if conditions:
        # Als we al een WHERE clausule hebben van het niet-eindpunten filter, gebruik AND
        if "WHERE" in base_query:
            base_query += " AND " + " AND ".join(conditions)
        else:
            base_query += " WHERE " + " AND ".join(conditions)
    
    # Zorg voor niet-null waarden voor kwalificaties als dat het veld is
    if field == "qualifiers":
        # Als we al condities hebben, voeg AND toe, anders voeg WHERE toe
        if conditions or "WHERE" in base_query:
            base_query += " AND ts.qualifiers IS NOT NULL AND ts.qualifiers != ''"
        else:
            base_query += " WHERE ts.qualifiers IS NOT NULL AND ts.qualifiers != ''"
    
    # Voeg order by toe
    base_query += f" ORDER BY ts.{field}"
    
    try:
        results = run_async_search(lambda: execute_custom_query(base_query))
        filtered_options = [row[field] for row in results.results] if results and hasattr(results, 'results') else []
        return filtered_options
    except Exception as e:
        st.error(f"Fout bij filteren van opties: {str(e)}")
        return []

def display_time_series_search():
    """Geef de tijdreeks-zoekinterface weer"""
    st.subheader("Tijdreeks Zoeken")
    
    # Controleer op en verwerk eindpuntwijzigingsvlag
    if "endpoint_changed" in st.session_state and st.session_state.endpoint_changed:
        st.write("Filters bijgewerkt op basis van eindpuntselectie")
        st.session_state.endpoint_changed = False
    
    # Initialiseer sessie-state voor filters als deze niet bestaat
    if "ts_filter_selections" not in st.session_state:
        st.session_state.ts_filter_selections = {
            "parameter_id": None,
            "qualifier": None,
            "module_instance": None,
            "endpoint": None
        }
        
    # Initialiseer of update filteropties
    if "ts_filter_options" not in st.session_state:
        with st.spinner("Tijdreeksopties laden..."):
            st.session_state.ts_filter_options = get_timeseries_options()
            
    # Definieer filter update callbacks
    def on_parameter_change():
        # Sla de nieuwe parameterwaarde op
        st.session_state.ts_filter_selections["parameter_id"] = st.session_state.parameter_select
        
        # Update de gefilterde opties voor kwalificaties en module-instanties
        if st.session_state.parameter_select:
            st.session_state.filtered_qualifiers = filter_timeseries_options(
                "qualifiers", 
                selected_parameter=st.session_state.parameter_select,
                selected_module=st.session_state.ts_filter_selections["module_instance"],
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
            st.session_state.filtered_modules = filter_timeseries_options(
                "modins",
                selected_parameter=st.session_state.parameter_select,
                selected_qualifier=st.session_state.ts_filter_selections["qualifier"],
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
        else:
            # Reset naar volledige lijsten als parameter is gewist
            st.session_state.filtered_qualifiers = st.session_state.ts_filter_options["qualifiers"]
            st.session_state.filtered_modules = st.session_state.ts_filter_options["module_instances"]
            
        # Zorg dat we kwalificatie- of moduleselecties niet verliezen als ze nog steeds geldige opties zijn
        if (st.session_state.ts_filter_selections["qualifier"] and 
            st.session_state.ts_filter_selections["qualifier"] not in st.session_state.filtered_qualifiers):
            st.session_state.ts_filter_selections["qualifier"] = None
            
        if (st.session_state.ts_filter_selections["module_instance"] and
            st.session_state.ts_filter_selections["module_instance"] not in st.session_state.filtered_modules):
            st.session_state.ts_filter_selections["module_instance"] = None
    
    def on_qualifier_change():
        # Sla de nieuwe kwalificatiewaarde op
        st.session_state.ts_filter_selections["qualifier"] = st.session_state.qualifier_select
        
        # Update de gefilterde opties voor parameters en module-instanties
        if st.session_state.qualifier_select:
            st.session_state.filtered_parameters = filter_timeseries_options(
                "parid",
                selected_qualifier=st.session_state.qualifier_select,
                selected_module=st.session_state.ts_filter_selections["module_instance"],
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
            st.session_state.filtered_modules = filter_timeseries_options(
                "modins",
                selected_parameter=st.session_state.ts_filter_selections["parameter_id"],
                selected_qualifier=st.session_state.qualifier_select,
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
        else:
            # Reset naar volledige lijsten als kwalificatie is gewist
            st.session_state.filtered_parameters = st.session_state.ts_filter_options["parameter_ids"]
            st.session_state.filtered_modules = st.session_state.ts_filter_options["module_instances"]
            
        # Zorg dat we parameter- of moduleselecties niet verliezen als ze nog steeds geldige opties zijn
        if (st.session_state.ts_filter_selections["parameter_id"] and 
            st.session_state.ts_filter_selections["parameter_id"] not in st.session_state.filtered_parameters):
            st.session_state.ts_filter_selections["parameter_id"] = None
            
        if (st.session_state.ts_filter_selections["module_instance"] and
            st.session_state.ts_filter_selections["module_instance"] not in st.session_state.filtered_modules):
            st.session_state.ts_filter_selections["module_instance"] = None
    
    def on_module_change():
        # Sla de nieuwe modulewaarde op
        st.session_state.ts_filter_selections["module_instance"] = st.session_state.module_select
        
        # Update de gefilterde opties voor parameters en kwalificaties
        if st.session_state.module_select:
            st.session_state.filtered_parameters = filter_timeseries_options(
                "parid",
                selected_qualifier=st.session_state.ts_filter_selections["qualifier"],
                selected_module=st.session_state.module_select,
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
            st.session_state.filtered_qualifiers = filter_timeseries_options(
                "qualifiers",
                selected_parameter=st.session_state.ts_filter_selections["parameter_id"],
                selected_module=st.session_state.module_select,
                selected_endpoint=st.session_state.ts_filter_selections["endpoint"]
            )
        else:
            # Reset naar volledige lijsten als module is gewist
            st.session_state.filtered_parameters = st.session_state.ts_filter_options["parameter_ids"]
            st.session_state.filtered_qualifiers = st.session_state.ts_filter_options["qualifiers"]
            
        # Zorg dat we parameter- of kwalificatieselecties niet verliezen als ze nog steeds geldige opties zijn
        if (st.session_state.ts_filter_selections["parameter_id"] and 
            st.session_state.ts_filter_selections["parameter_id"] not in st.session_state.filtered_parameters):
            st.session_state.ts_filter_selections["parameter_id"] = None
            
        if (st.session_state.ts_filter_selections["qualifier"] and
            st.session_state.ts_filter_selections["qualifier"] not in st.session_state.filtered_qualifiers):
            st.session_state.ts_filter_selections["qualifier"] = None
            
    def on_endpoint_change():
        # Sla de nieuwe eindpuntwaarde op
        st.session_state.ts_filter_selections["endpoint"] = st.session_state.endpoint_select
        
        # Update de gefilterde opties voor alle andere velden
        try:
            st.session_state.filtered_parameters = filter_timeseries_options(
                "parid",
                selected_qualifier=st.session_state.ts_filter_selections["qualifier"],
                selected_module=st.session_state.ts_filter_selections["module_instance"],
                selected_endpoint=st.session_state.endpoint_select
            )
            
            st.session_state.filtered_qualifiers = filter_timeseries_options(
                "qualifiers",
                selected_parameter=st.session_state.ts_filter_selections["parameter_id"],
                selected_module=st.session_state.ts_filter_selections["module_instance"],
                selected_endpoint=st.session_state.endpoint_select
            )
            
            st.session_state.filtered_modules = filter_timeseries_options(
                "modins",
                selected_parameter=st.session_state.ts_filter_selections["parameter_id"],
                selected_qualifier=st.session_state.ts_filter_selections["qualifier"],
                selected_endpoint=st.session_state.endpoint_select
            )
        except Exception as e:
            st.error(f"Fout bij bijwerken opties na eindpuntwijziging: {str(e)}")
            
        # Zorg dat we andere selecties niet verliezen als ze nog steeds geldig zijn
        if (st.session_state.ts_filter_selections["parameter_id"] and 
            st.session_state.ts_filter_selections["parameter_id"] not in st.session_state.filtered_parameters):
            st.session_state.ts_filter_selections["parameter_id"] = None
            
        if (st.session_state.ts_filter_selections["qualifier"] and
            st.session_state.ts_filter_selections["qualifier"] not in st.session_state.filtered_qualifiers):
            st.session_state.ts_filter_selections["qualifier"] = None
            
        if (st.session_state.ts_filter_selections["module_instance"] and
            st.session_state.ts_filter_selections["module_instance"] not in st.session_state.filtered_modules):
            st.session_state.ts_filter_selections["module_instance"] = None
            
        # Zet vlaggen om rerun te triggeren nadat state is bijgewerkt
        st.session_state.endpoint_changed = True
    
    # Stel gefilterde opties in als deze nog niet in sessie-state zitten
    if "filtered_parameters" not in st.session_state:
        st.session_state.filtered_parameters = st.session_state.ts_filter_options["parameter_ids"]
    if "filtered_qualifiers" not in st.session_state:
        st.session_state.filtered_qualifiers = st.session_state.ts_filter_options["qualifiers"]
    if "filtered_modules" not in st.session_state:
        st.session_state.filtered_modules = st.session_state.ts_filter_options["module_instances"]
    
    # Maak de filter UI
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.selectbox(
            "Module Instantie ID",
            options=[""] + st.session_state.filtered_modules,
            key="module_select",
            on_change=on_module_change,
            index=0 if not st.session_state.ts_filter_selections["module_instance"] else 
                  1 + st.session_state.filtered_modules.index(st.session_state.ts_filter_selections["module_instance"]),
            help="Selecteer een module instantie uit de lijst"
        )
    
    with col2:
        st.selectbox(
            "Parameter ID",
            options=[""] + st.session_state.filtered_parameters,
            key="parameter_select",
            on_change=on_parameter_change,
            index=0 if not st.session_state.ts_filter_selections["parameter_id"] else 
                  1 + st.session_state.filtered_parameters.index(st.session_state.ts_filter_selections["parameter_id"]),
            help="Selecteer een parameter ID uit de lijst"
        ) 

    with col3:
        st.selectbox(
            "Kwalificatie",
            options=[""] + st.session_state.filtered_qualifiers,
            key="qualifier_select",
            on_change=on_qualifier_change,
            index=0 if not st.session_state.ts_filter_selections["qualifier"] else 
                  1 + st.session_state.filtered_qualifiers.index(st.session_state.ts_filter_selections["qualifier"]),
            help="Selecteer een kwalificatie uit de lijst"
        )
        
    with col4:
        # Maak een dropdown met speciale opties en eindpuntbeschrijvingen 
        if "endpoint_descriptions" in st.session_state.ts_filter_options:
            # Voeg twee speciale opties toe: Alle (None) en Elk Eindpunt (True)
            endpoint_options = ["Alle", "Elk Eindpunt"] + st.session_state.ts_filter_options["endpoint_descriptions"]
            
            # Zorg dat de eindpuntsleutel bestaat in ts_filter_selections
            if "endpoint" not in st.session_state.ts_filter_selections:
                st.session_state.ts_filter_selections["endpoint"] = None
                
            # Stel de index in voor het momenteel geselecteerde eindpunt
            selected_index = 0  # Standaard naar "Alle"
            current_endpoint = st.session_state.ts_filter_selections["endpoint"]
            
            # Bepaal de juiste index voor de dropdown
            if current_endpoint is True:  # Boolean True - Elk Eindpunt
                selected_index = 1
            elif current_endpoint is not None and isinstance(current_endpoint, str):
                # String beschrijving - specifiek eindpunt
                try:
                    # Tel 2 erbij op omdat "Alle" en "Elk Eindpunt" de eerste opties zijn
                    selected_index = 2 + st.session_state.ts_filter_options["endpoint_descriptions"].index(current_endpoint)
                except ValueError:
                    # Als niet gevonden, standaard naar "Alle"
                    selected_index = 0
                
            # Maak de selectbox voor eindpuntfiltering
            st.selectbox(
                "Eindpunt",
                options=endpoint_options,
                key="endpoint_select_display",
                index=selected_index,
                help="Filter op eindpuntstatus of -beschrijving"
            )
            
            # Bewaar vorige waarde voor wijzigingsdetectie
            if "prev_endpoint_display" not in st.session_state:
                st.session_state.prev_endpoint_display = st.session_state.endpoint_select_display
                
            # Update sessie-state met het geselecteerde eindpunt
            if st.session_state.endpoint_select_display != st.session_state.prev_endpoint_display:
                # Vertaal de weergavewaarde naar de daadwerkelijke waarde
                if st.session_state.endpoint_select_display == "Alle":
                    st.session_state.endpoint_select = None
                elif st.session_state.endpoint_select_display == "Elk Eindpunt":
                    st.session_state.endpoint_select = True
                else:
                    # Een specifieke eindpuntbeschrijving
                    st.session_state.endpoint_select = st.session_state.endpoint_select_display
                
                # Bewaar voor volgende wijziging
                st.session_state.prev_endpoint_display = st.session_state.endpoint_select_display
                
                # Roep de on_change handler expliciet aan
                if "prev_endpoint_select" not in st.session_state:
                    st.session_state.prev_endpoint_select = st.session_state.endpoint_select
                
                if st.session_state.prev_endpoint_select != st.session_state.endpoint_select:
                    st.session_state.prev_endpoint_select = st.session_state.endpoint_select
                    on_endpoint_change()
                    # Forceer rerun om UI bij te werken met nieuwe gefilterde opties
                    st.rerun()
        
    search_button = st.button("Zoek Tijdreeksen", key="search_timeseries_button", use_container_width=True)
    
    if search_button:
        parameter_id = st.session_state.ts_filter_selections["parameter_id"]
        qualifier = st.session_state.ts_filter_selections["qualifier"]
        module_instance = st.session_state.ts_filter_selections["module_instance"]
        endpoint = st.session_state.ts_filter_selections["endpoint"]
        
        if parameter_id or qualifier or module_instance or endpoint is not None:
            with st.spinner("Tijdreeksen zoeken..."):
                try:
                    results = run_async_search(
                        st.session_state.tools_interface.search_timeseries,
                        parameter_id=parameter_id,
                        qualifier_pattern=qualifier,
                        module_instance=module_instance,
                        endpoint=endpoint
                    )
                    # Sla de zoekresultaten op in sessie-state
                    st.session_state.timeseries_search_results = results
                    display_timeseries_results(results)
                except Exception as e:
                    st.error(f"Fout bij zoeken tijdreeksen: {str(e)}")
        else:
            st.warning("Selecteer ten minste één zoekcriterium.")
    # Toon opgeslagen resultaten als ze bestaan
    elif "timeseries_search_results" in st.session_state:
        display_timeseries_results(st.session_state.timeseries_search_results)
    
    # Toon tijdreeksdetails indien gevraagd
    if "timeseries_details_view_active" in st.session_state and st.session_state.timeseries_details_view_active:
        st.subheader(f"Tijdreeks Details voor ID: {st.session_state.selected_timeseries_id}")
        
        include_transformations = st.checkbox("Toon gerelateerde transformaties", value=True,
                                            help="Toon transformaties die deze tijdreeks gebruiken")
        
        with st.spinner("Tijdreeks details laden..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.describe_timeseries,
                    timeseries_id=st.session_state.selected_timeseries_id,
                    include_transformations=include_transformations
                )
                st.markdown(details.markdown_content)
                
                # Knop om afhankelijkheden te visualiseren
                if st.button("Visualiseer Tijdreeks", key="visualize_timeseries"):
                    with st.spinner("Tijdreeksvisualisatie genereren..."):
                        graph = run_async_search(
                            st.session_state.tools_interface.visualize_graph,
                            root_entity_id=st.session_state.selected_timeseries_id,
                            root_entity_type="timeseries",
                            max_depth=3,
                            max_nodes=50,
                            include_properties=True,
                            direction="LR"
                        )
                        
                        # Extraheer en verbeter het mermaid-diagram als het bestaat
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', graph.markdown_content, re.DOTALL)
                        if mermaid_match:
                            mermaid_code = mermaid_match.group(1)
                            # Schat geschikte hoogte
                            height = estimate_diagram_height(mermaid_code)
                            render_mermaid(mermaid_code, height=height)
                        else:
                            st.markdown(graph.markdown_content)
                
                # Knop om afhankelijkheden te analyseren
                if st.button("Analyseer Afhankelijkheden", key="analyze_timeseries_deps"):
                    with st.spinner("Tijdreeks afhankelijkheden analyseren..."):
                        deps = run_async_search(
                            st.session_state.tools_interface.analyze_dependencies,
                            entity_id=st.session_state.selected_timeseries_id,
                            entity_type="timeseries"
                        )
                        
                        # Extraheer en verbeter het mermaid-diagram als het bestaat
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', deps.markdown_content, re.DOTALL)
                        if mermaid_match:
                            # Toon tekstinhoud voor het diagram
                            content_before = deps.markdown_content.split('```mermaid')[0]
                            if content_before.strip():
                                st.markdown(content_before)
                            
                            mermaid_code = mermaid_match.group(1)
                            # Schat geschikte hoogte
                            height = estimate_diagram_height(mermaid_code)
                            render_mermaid(mermaid_code, height=height)
                            
                            # Toon eventuele tekstinhoud na het diagram
                            content_after = deps.markdown_content.split('```')[2]
                            if content_after.strip():
                                st.markdown(content_after)
                        else:
                            st.markdown(deps.markdown_content)
                
                # Knop om details te sluiten
                if st.button("Sluit Details", key="close_timeseries_details"):
                    st.session_state.timeseries_details_view_active = False
                    st.rerun()
            except Exception as e:
                st.error(f"Fout bij laden tijdreeksdetails: {str(e)}")

    # Voeg een wis-knop toe voor tijdreeks zoekacties
    if "timeseries_search_results" in st.session_state:
        if st.button("Wis Resultaten", key="clear_timeseries_results"):
            del st.session_state.timeseries_search_results
            st.rerun()

# Gebruik tabs voor verschillende zoektypes
tab1, tab2, tab3 = st.tabs(["Tijdreeks Zoeken", "Workflow Zoeken", "Zoek Transformaties"])

with tab1:
    st.header("Zoek Tijdreeksen")
    
    display_time_series_search()

with tab2:
    st.header("Zoek Workflows")
    
    st.write("Voer zoektermen in om workflows te vinden. Resultaten worden automatisch bijgewerkt terwijl u typt.")
    
    workflow_name = st.text_input("Workflow Naam of Beschrijving", key="workflow_name", 
                                  help="Voer een patroon in om workflow-namen of beschrijvingen te matchen")
    
    # Maak een container voor de resultaten
    workflow_results_container = st.container()
    
    # Auto-zoekfunctie die wordt uitgevoerd wanneer invoer verandert
    def search_workflows():
        with workflow_results_container:
            with st.spinner("Workflows zoeken..."):
                try:
                    # Gebruik '%' als standaardpatroon als leeg
                    pattern = workflow_name if workflow_name else "%"
                    results = run_async_search(
                        st.session_state.tools_interface.search_workflows,
                        name_pattern=pattern
                    )
                    
                    if results.results:
                        # Converteer resultaten naar DataFrame voor betere weergave
                        data = []
                        for workflow in results.results:
                            data.append({
                                "ID": workflow.id,
                                "Workflow ID": workflow.wf_id,
                                "Beschrijving": workflow.desc,
                                "Module Config IDs": ', '.join(workflow.module_config_ids) if workflow.module_config_ids else 'Geen'
                            })
                        
                        df = pd.DataFrame(data)
                        
                        # Voeg sorteeropties toe
                        sort_column = st.selectbox("Sorteer op", ["ID", "Workflow ID", "Beschrijving", "Module Config IDs"], key="workflow_sort")
                        sort_ascending = st.checkbox("Oplopende volgorde", True, key="workflow_sort_order")
                        
                        # Sorteer en toon als tabel
                        df_sorted = df.sort_values(by=sort_column, ascending=sort_ascending)
                        st.dataframe(df_sorted, use_container_width=True)
                        
                        # Download optie
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download resultaten als CSV",
                            data=csv,
                            file_name="workflow_zoekresultaten.csv",
                            mime="text/csv"
                        )
                        
                        # Bekijk details opties
                        st.subheader("Bekijk Workflow Details")
                        
                        # Maak een callback functie om de detailweergave bij te werken wanneer selectie verandert
                        def on_workflow_select():
                            st.session_state.selected_workflow_id = st.session_state.workflow_selector
                            st.session_state.workflow_details_view_active = True
                            
                        # Gebruik de on_change parameter om update te triggeren wanneer selectie verandert
                        selected_workflow = st.selectbox(
                            "Selecteer een workflow om details te bekijken",
                            options=df["ID"].tolist(),
                            format_func=lambda x: f"{x} - {df.loc[df['ID'] == x, 'Workflow ID'].iloc[0]}",
                            key="workflow_selector",
                            on_change=on_workflow_select
                        )
                    else:
                        st.info(f"Geen workflows gevonden die overeenkomen met het patroon '{pattern}'.")
                except Exception as e:
                    st.error(f"Fout bij zoeken naar workflows: {str(e)}")
    
    # Trigger zoekactie automatisch wanneer de invoer verandert
    if "prev_workflow_name" not in st.session_state:
        st.session_state.prev_workflow_name = ""
    
    # Controleer of de invoer is gewijzigd
    if workflow_name != st.session_state.prev_workflow_name:
        st.session_state.prev_workflow_name = workflow_name
        search_workflows()
    else:
        search_workflows()
    
    # Toon workflow details indien gevraagd
    if "workflow_details_view_active" in st.session_state and st.session_state.workflow_details_view_active:
        st.header("Workflow Details")
        
        with st.spinner("Workflow details laden..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.get_workflow_details,
                    workflow_id=st.session_state.selected_workflow_id
                )
                
                # Extraheer workflow details direct uit de resultaten
                workflow = details.results[0]
                
                # Toon de workflowstructuur direct met het diagram
                st.markdown("### Workflow Structuur")
                
                try:
                    # Maak nodes voor het flowdiagram
                    nodes = []
                    edges = []
                    
                    # 1. Voeg workflow node toe (startnode)
                    workflow_node = StreamlitFlowNode(
                        id=str(workflow.id),
                        pos=(100, 100),
                        data={'content': workflow.wf_id, 'description': workflow.desc},
                        node_type='input',
                        source_position='right',
                        draggable=False
                    )
                    nodes.append(workflow_node)
                    
                    # 2. Voeg module nodes toe
                    module_y = 50
                    module_y_step = 100
                    
                    for i, module_call in enumerate(workflow.module_calls):
                        module_id = f"module_{module_call.mic_id}"
                        module_name = module_call.modins
                        
                        # Positioneer modules verticaal
                        y_pos = module_y + i * module_y_step
                        
                        # Voeg module node toe
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
                        
                        # Voeg rand toe van workflow naar module
                        edge = StreamlitFlowEdge(
                            id=f"edge_wf_to_{module_id}",
                            source=str(workflow.id),
                            target=module_id,
                            animated=True,
                            marker_end={'type': 'arrow'}
                        )
                        edges.append(edge)
                    
                    # Maak een goede flow-id
                    flow_key = f"workflow_flow_{workflow.id}"
                    
                    # Initialiseer de state als deze niet bestaat in sessie-state
                    if flow_key not in st.session_state:
                        st.session_state[flow_key] = StreamlitFlowState(nodes, edges)
                    
                    # Vang de bijgewerkte state op met geselecteerde node/edge
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
                    
                    # Toon welke node was geselecteerd, indien van toepassing
                    if updated_state and updated_state.selected_id:
                        selected_node_id = updated_state.selected_id
                        st.write(f"### Geselecteerd: {selected_node_id}")
                        
                        # Controleer of de geselecteerde node de workflow is
                        if selected_node_id == str(workflow.id):
                            st.write("#### Workflow Details")
                            st.write(f"**ID:** {workflow.id}")
                            st.write(f"**Naam:** {workflow.wf_id}")
                            st.write(f"**Beschrijving:** {workflow.desc}")
                            st.write(f"**Functie:** {workflow.wffn}")
                            
                        # Controleer of de geselecteerde node een module is
                        elif selected_node_id.startswith("module_"):
                            module_id = int(selected_node_id.replace("module_", ""))
                            module = next((m for m in workflow.module_calls if m.mic_id == module_id), None)
                            
                            if module:
                                st.write("#### Module Details")
                                st.write(f"**ID:** {module.mic_id}")
                                st.write(f"**Naam:** {module.modins}")
                                st.write(f"**Volgorde:** {module.ord_nr}")
                                
                                # Toon direct transformaties voor deze module
                                st.write("#### Transformaties in deze module:")
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
                                        # Maak een dataframe voor transformaties
                                        trafo_data = []
                                        for trafo in trafo_results.results:
                                            trafo_data.append({
                                                "Volgorde": trafo['ord_nr'],
                                                "ID": trafo['id'],
                                                "Beschrijving": trafo['desc']
                                            })
                                        
                                        if trafo_data:
                                            trafo_df = pd.DataFrame(trafo_data)
                                            st.dataframe(trafo_df, use_container_width=True)
                                        else:
                                            st.write("Geen transformaties gevonden voor deze module.")
                                    else:
                                        st.write("Geen transformaties gevonden voor deze module.")
                                except Exception as e:
                                    st.warning(f"Kon transformaties voor module {module.modins} niet laden: {str(e)}")
                    
                    # Verwijder extra knoppen, behoud alleen de Sluit Details knop
                    if st.button("Sluit Details", key="close_workflow_details"):
                        # Ruim flow state op bij het sluiten van details
                        flow_key = f"workflow_flow_{workflow.id}"
                        if flow_key in st.session_state:
                            del st.session_state[flow_key]
                            
                        st.session_state.workflow_details_view_active = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Fout bij maken flowdiagram: {str(e)}")
                    # Print volledige traceback voor debugging
                    import traceback
                    st.code(traceback.format_exc())
                    
                    # Terugvallen op eenvoudige weergave
                    st.write("#### Module-aanroepen en Transformaties")
                    
                    for module_call in workflow.module_calls:
                        module_name = module_call.modins
                        st.write(f"**Module:** {module_name}")
                        
                        # Haal transformaties op voor deze module
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
                                # Maak een dataframe voor transformaties
                                trafo_data = []
                                for trafo in trafo_results.results:
                                    trafo_data.append({
                                        "Volgorde": trafo['ord_nr'],
                                        "ID": trafo['id'],
                                        "Beschrijving": trafo['desc']
                                    })
                                
                                trafo_df = pd.DataFrame(trafo_data)
                                st.dataframe(trafo_df, use_container_width=True)
                            else:
                                st.write("Geen transformaties gevonden voor deze module.")
                                
                        except Exception as e:
                            st.warning(f"Kon transformaties voor module {module_name} niet laden: {str(e)}")
            
            except Exception as e:
                st.error(f"Fout bij laden workflow details: {str(e)}")

with tab3:
    st.header("Zoek Transformaties")
    
    col1, col2 = st.columns(2)
    
    with col1:
        transformation_desc = st.text_input("Transformatie Beschrijving", key="transformation_desc",
                                          help="Voer een beschrijvingspatroon in, bijv. 'interpolatie'")
    
    col1, col2 = st.columns(2)
    
    with col1:
        workflow_name_filter = st.text_input("Workflow Naam (Optioneel)", key="workflow_name_filter",
                                           help="Filter op workflow naam")
    
    with col2:
        module_config_filter = st.text_input("Module Config (Optioneel)", key="module_config_filter",
                                           help="Filter op module configuratie")
    
    search_button = st.button("Zoek Transformaties", key="search_transformation_button", use_container_width=True)
    
    if search_button:
        if transformation_desc:
            with st.spinner("Transformaties zoeken..."):
                try:
                    results = run_async_search(
                        st.session_state.tools_interface.search_transformations,
                        description_pattern=transformation_desc,
                        workflow_name=workflow_name_filter if workflow_name_filter else None,
                        module_config=module_config_filter if module_config_filter else None
                    )
                    # Sla de zoekresultaten op in sessie-state
                    st.session_state.transformation_search_results = results
                    display_transformation_results(results)
                except Exception as e:
                    st.error(f"Fout bij zoeken naar transformaties: {str(e)}")
        else:
            st.warning("Voer een transformatiebeschrijving in.")
    # Toon opgeslagen resultaten als ze bestaan
    elif "transformation_search_results" in st.session_state:
        display_transformation_results(st.session_state.transformation_search_results)
    
    # Toon transformatie details indien gevraagd
    if "transformation_details_view_active" in st.session_state and st.session_state.transformation_details_view_active:
        with st.spinner("Transformatie details laden..."):
            try:
                details = run_async_search(
                    st.session_state.tools_interface.get_transformation_details,
                    transformation_id=st.session_state.selected_transformation_id
                )
                
                # In plaats van ruwe markdown weer te geven, maak een mooiere lay-out
                if details and details.results:
                    trafo = details.results[0]
                    
                    # Gebruik subheader in plaats van header om dezelfde grootte te behouden als "Bekijk Transformatie Details"
                    st.subheader(f"Transformatie {trafo.id}: {trafo.desc}")
                    
                    # Toon basisinformatie in een nette expander
                    with st.expander("Basisinformatie", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Module Instantie", trafo.modins)
                            st.metric("Volgnummer", trafo.ord_nr)
                        with col2:
                            st.metric("Module Config ID", trafo.mic_id)
                            # Voeg link toe om deze module in de workflow te bekijken
                            if st.button("Bekijk in Workflow"):
                                # Haal de workflow ID op via de API
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
                    
                    # Verplaats Transformation Flow hier naar boven, direct na basisinformatie
                    # Toon transformatie flow visualisatie indien beschikbaar
                    visualize_section = [line for line in details.markdown_content.split('\n') if "Transformation Flow" in line]
                    if visualize_section:
                        st.write("**Transformatie Flow**")
                        # Extraheer en toon het mermaid-diagram indien aanwezig
                        mermaid_match = re.search(r'```mermaid\n(.*?)```', details.markdown_content, re.DOTALL)
                        if mermaid_match:
                            # Gebruik onze aangepaste mermaid-renderer in plaats van st.markdown
                            mermaid_code = mermaid_match.group(1)
                            # Schat geschikte hoogte
                            height = estimate_diagram_height(mermaid_code)
                            render_mermaid(mermaid_code, height=height)
                        else:
                            st.info("Geen flowdiagram beschikbaar voor deze transformatie.")
                    
                    # Toon tijdreeks connecties met betere opmaak
                    st.write("**Tijdreeks Verbindingen**")
                    
                    # Toon de input en output tijdreeksen in tabs voor betere organisatie
                    input_ts = [ts for ts in trafo.time_series_links if ts.inout == "in"]
                    output_ts = [ts for ts in trafo.time_series_links if ts.inout == "out"]
                    
                    in_tab, out_tab = st.tabs(["Input Tijdreeksen", "Output Tijdreeksen"])
                    
                    with in_tab:
                        if input_ts:
                            # Maak een DataFrame voor betere weergave
                            input_data = []
                            for ts in input_ts:
                                # Haal de tijdreeks details op
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
                                        "Kwalificaties": ts_info["qualifiers"] or "-"
                                    })
                            
                            if input_data:
                                st.dataframe(pd.DataFrame(input_data), use_container_width=True)
                                
                                # Voeg knop toe om input tijdreeksdetails te bekijken
                                if len(input_data) > 0:
                                    if st.button("Bekijk Input Tijdreeks Details"):
                                        st.session_state.selected_timeseries_id = input_data[0]["ID"]
                                        st.session_state.timeseries_details_view_active = True
                                        st.rerun()
                        else:
                            st.info("Deze transformatie heeft geen input tijdreeksen. Dit kan zijn omdat het een generatie/creatie transformatie is die nieuwe data produceert zonder inputs, of omdat inputs via andere mechanismen zijn gedefinieerd zoals vaste parameters of database queries.")
                    
                    with out_tab:
                        if output_ts:
                            # Maak een DataFrame voor betere weergave
                            output_data = []
                            for ts in output_ts:
                                # Haal de tijdreeks details op
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
                                        "Kwalificaties": ts_info["qualifiers"] or "-"
                                    })
                            
                            if output_data:
                                st.dataframe(pd.DataFrame(output_data), use_container_width=True)
                                
                                # Voeg knop toe om output tijdreeksdetails te bekijken
                                if len(output_data) > 0:
                                    if st.button("Bekijk Output Tijdreeks Details"):
                                        st.session_state.selected_timeseries_id = output_data[0]["ID"]
                                        st.session_state.timeseries_details_view_active = True
                                        st.rerun()
                        else:
                            st.info("Deze transformatie heeft geen output tijdreeksen. Dit is ongebruikelijk maar kan voorkomen bij transformaties die operaties uitvoeren maar geen tijdreeksoutputs produceren (bijv. database updates, bestandsexports).")
                    
                    # Voeg knoppen toe voor aanvullende acties
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Knop om afhankelijkheden te visualiseren
                        if st.button("Visualiseer Transformatie", key="visualize_transformation"):
                            with st.spinner("Transformatie visualisatie genereren..."):
                                # Haal eerst gedetailleerde informatie op over de transformatie
                                t_details = run_async_search(
                                    st.session_state.tools_interface.get_transformation_details,
                                    transformation_id=st.session_state.selected_transformation_id
                                )
                                
                                # Maak daarna de visualisatie met extra parameters
                                graph = run_async_search(
                                    st.session_state.tools_interface.visualize_graph,
                                    root_entity_id=st.session_state.selected_transformation_id,
                                    root_entity_type="transformation",
                                    max_depth=3,
                                    max_nodes=50,
                                    include_properties=True,
                                    direction="LR"
                                )
                                # Extraheer het mermaid-diagram
                                mermaid_match = re.search(r'```mermaid\n(.*?)```', graph.markdown_content, re.DOTALL)
                                if mermaid_match:
                                    mermaid_code = mermaid_match.group(1)
                                    height = estimate_diagram_height(mermaid_code)
                                    render_mermaid(mermaid_code, height=height)
                                else:
                                    st.markdown(graph.markdown_content)
                    
                    with col2:
                        # Knop om afhankelijkheden te analyseren
                        if st.button("Analyseer Afhankelijkheden", key="analyze_transformation_deps"):
                            with st.spinner("Transformatie afhankelijkheden analyseren..."):
                                deps = run_async_search(
                                    st.session_state.tools_interface.analyze_dependencies,
                                    entity_id=st.session_state.selected_transformation_id,
                                    entity_type="transformation"
                                )
                                # Extraheer en render het mermaid-diagram indien aanwezig
                                mermaid_match = re.search(r'```mermaid\n(.*?)```', deps.markdown_content, re.DOTALL)
                                if mermaid_match:
                                    # Toon tekstinhoud voor het diagram
                                    content_before = deps.markdown_content.split('```mermaid')[0]
                                    if content_before.strip():
                                        st.markdown(content_before)
                                    
                                    mermaid_code = mermaid_match.group(1)
                                    # Schat geschikte hoogte
                                    height = estimate_diagram_height(mermaid_code)
                                    render_mermaid(mermaid_code, height=height)
                                    
                                    # Toon eventuele tekstinhoud na het diagram
                                    content_after = deps.markdown_content.split('```')[2]
                                    if content_after.strip():
                                        st.markdown(content_after)
                                else:
                                    st.markdown(deps.markdown_content)
                    
                    with col3:
                        # Knop om details te sluiten
                        if st.button("Sluit Details", key="close_transformation_details"):
                            st.session_state.transformation_details_view_active = False
                            st.rerun()
                else:
                    st.error("Geen details beschikbaar voor deze transformatie.")
            except Exception as e:
                st.error(f"Fout bij laden transformatie details: {str(e)}")

    # Voeg een wis-knop toe voor transformatie zoekacties
    if "transformation_search_results" in st.session_state:
        if st.button("Wis Resultaten", key="clear_transformation_results"):
            del st.session_state.transformation_search_results
            st.rerun()

# Render footer
render_footer() 