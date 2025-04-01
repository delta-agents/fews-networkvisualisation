import streamlit as st
import pandas as pd
import altair as alt
import asyncio

def run_async_function(async_function, **kwargs):
    """Run an async function and return the results."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_function(**kwargs))
    finally:
        loop.close()

def render_dead_points_tab():
    """Render the dead points analysis tab"""
    st.subheader("Dode Punten Analyse")
    
    st.markdown("""
    Deze analyse toont tijdreeksen die worden gegenereerd maar nooit worden gebruikt als invoer
    voor andere transformaties en niet zijn gemarkeerd als eindpunten.
    """)
    
    with st.spinner("Dode punten analyseren..."):
        try:
            # Run the dead points analysis
            results = st.session_state.tools_interface.analyze_dead_points(include_producers=True)
            
            if results:
                # Display summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Dode Punten", results.count)
                # Create DataFrame for dead points
                if results.dead_points:
                    dead_points_data = []
                    for dp in results.dead_points:
                        dp_dict = {
                            "ID": dp.id,
                            "Module": dp.modins,
                            "Parameter": dp.parid,
                            "Qualifiers": dp.qualifiers,
                            "TSType": dp.tstype,
                            "Tijdstap": dp.timess,
                            "ValueType": dp.vtype
                        }
                        dead_points_data.append(dp_dict)
                    
                    df = pd.DataFrame(dead_points_data)
                    
                    # Define display columns
                    display_columns = ["Module", "Parameter", "TSType", "Tijdstap"]
                    
                    # Add filtering options
                    st.subheader("Filter Dode Punten")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if len(df["Module"].unique()) > 1:
                            module_filter = st.multiselect(
                                "Filter op Module",
                                options=sorted(df["Module"].unique()),
                                default=[],
                                key="dead_points_module_filter"
                            )
                        else:
                            module_filter = []
                    
                    with col2:
                        if len(df["Parameter"].unique()) > 1:
                            param_filter = st.multiselect(
                                "Filter op Parameter",
                                options=sorted(df["Parameter"].unique()),
                                default=[],
                                key="dead_points_param_filter"
                            )
                        else:
                            param_filter = []
                    
                    with col3:
                        if len(df["TSType"].unique()) > 1:
                            tstype_filter = st.multiselect(
                                "Filter op TSType",
                                options=sorted(df["TSType"].unique()),
                                default=[],
                                key="dead_points_tstype_filter"
                            )
                        else:
                            tstype_filter = []
                    
                    # Apply filters
                    filtered_df = df.copy()
                    if module_filter:
                        filtered_df = filtered_df[filtered_df["Module"].isin(module_filter)]
                    if param_filter:
                        filtered_df = filtered_df[filtered_df["Parameter"].isin(param_filter)]
                    if tstype_filter:
                        filtered_df = filtered_df[filtered_df["TSType"].isin(tstype_filter)]
                    
                    # Show counts
                    st.markdown(f"**Toont {len(filtered_df)} van {len(df)} dode punten**")
                    
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
                            
                            # Add to chat button with unique key using row ID and idx
                            if cols[0].button("💬", key=f"dead_point_btn_{row['ID']}_{idx}", use_container_width=True):
                                from .sidebar_chat import add_to_chat
                                # Create timeseries data with type
                                timeseries_data = row.to_dict()
                                timeseries_data["type"] = "timeseries"
                                add_to_chat(timeseries_data)
                            
                            # Display only the visible columns with code formatting for Module
                            for i, col_name in enumerate(display_columns):
                                if col_name == "Module":
                                    cols[i+1].code(row[col_name])
                                else:
                                    cols[i+1].write(row[col_name])
                            
                            # Add a subtle divider
                            st.divider()
                    
                    # Add download option
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="Download Dode Punten CSV",
                        data=csv,
                        file_name="dode_punten.csv",
                        mime="text/csv",
                        key="dead_points_download"
                    )
                
        except Exception as e:
            st.error(f"Fout bij analyseren van dode punten: {str(e)}")

def render_workflow_stats_tab():
    """Render the workflow statistics tab"""
    st.subheader("Workflow Statistieken")
    
    with st.spinner("Statistieken genereren..."):
        try:
            # Query for workflows with most transformations
            complex_workflows_query = """
            SELECT cs.id, cs.wf_id, cs.desc, COUNT(t.id) as transformation_count
            FROM call_stacks cs
            JOIN modins_calls mc ON cs.id = mc.call_stack_id
            JOIN trafos t ON mc.id = t.mic_id
            GROUP BY cs.id
            ORDER BY transformation_count DESC
            LIMIT 20
            """
            
            
            # Execute queries
            complex_results = st.session_state.tools_interface.execute_custom_query(query=complex_workflows_query)
            
            
            # Display complex workflows
            st.subheader("Complexe Workflows")
            if complex_results and complex_results.results:
                df = pd.DataFrame(complex_results.results)
                
                # Create visualization
                chart = alt.Chart(df).mark_bar().encode(
                    x=alt.X('wf_id:N', sort='-y', title='Workflow ID'),
                    y=alt.Y('transformation_count:Q', title='Aantal Transformaties'),
                    tooltip=['wf_id', 'desc', 'transformation_count']
                ).properties(
                    title='Top 20 Meest Complexe Workflows'
                )
                st.altair_chart(chart, use_container_width=True)
                
                # Show detailed table
                st.dataframe(df, use_container_width=True)
        
        except Exception as e:
            st.error(f"Fout bij genereren workflow statistieken: {str(e)}")

def render_db_stats_tab():
    """Render the database statistics tab"""
    st.subheader("Database Statistieken")
    
    with st.spinner("Statistieken genereren..."):
        try:
            # Query for overall statistics
            stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM call_stacks) as workflow_count,
                (SELECT COUNT(*) FROM modins_calls) as module_config_count,
                (SELECT COUNT(*) FROM ts_sets) as timeseries_count,
                (SELECT COUNT(*) FROM trafos) as transformation_count,
                (SELECT COUNT(*) FROM links) as link_count,
                (SELECT COUNT(*) FROM endpoints) as endpoint_count
            """
            
            # Execute query
            stats_results = st.session_state.tools_interface.execute_custom_query(query=stats_query)
            
            if stats_results and stats_results.results:
                stats = stats_results.results[0]
                
                # Display metrics in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Workflows", stats["workflow_count"])
                    st.metric("Module Configs", stats["module_config_count"])
                with col2:
                    st.metric("Tijdreeksen", stats["timeseries_count"])
                    st.metric("Transformaties", stats["transformation_count"])
                with col3:
                    st.metric("Links", stats["link_count"])
                    st.metric("Eindpunten", stats["endpoint_count"])
                
                # Create visualization
                data = pd.DataFrame({
                    "Type": ["Workflows", "Module Configs", "Tijdreeksen", 
                            "Transformaties", "Links", "Eindpunten"],
                    "Aantal": [stats["workflow_count"], stats["module_config_count"],
                             stats["timeseries_count"], stats["transformation_count"],
                             stats["link_count"], stats["endpoint_count"]]
                })
                
                chart = alt.Chart(data).mark_bar().encode(
                    x='Type:N',
                    y='Aantal:Q',
                    color='Type:N',
                    tooltip=['Type', 'Aantal']
                ).properties(
                    title='Database Entiteiten'
                )
                st.altair_chart(chart, use_container_width=True)
                
                # Calculate and display ratios
                st.subheader("Verhoudingen")
                ratio_col1, ratio_col2, ratio_col3 = st.columns(3)
                with ratio_col1:
                    st.metric("Tijdreeksen per Workflow", 
                            round(stats["timeseries_count"] / stats["workflow_count"], 1)
                            if stats["workflow_count"] > 0 else 0)
                with ratio_col2:
                    st.metric("Transformaties per Module Config",
                            round(stats["transformation_count"] / stats["module_config_count"], 1)
                            if stats["module_config_count"] > 0 else 0)
                with ratio_col3:
                    st.metric("Links per Transformatie",
                            round(stats["link_count"] / stats["transformation_count"], 1)
                            if stats["transformation_count"] > 0 else 0)
        
        except Exception as e:
            st.error(f"Fout bij genereren database statistieken: {str(e)}")

def render_reports_tab():
    """Render the reports tab content with subtabs"""
    st.header("Rapportages")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs([
        "Dode Punten",
        "Workflow Statistieken",
        "Database Statistieken"
    ])
    
    # Render content for each tab
    with tab1:
        render_dead_points_tab()
    
    with tab2:
        render_workflow_stats_tab()
    
    with tab3:
        render_db_stats_tab() 