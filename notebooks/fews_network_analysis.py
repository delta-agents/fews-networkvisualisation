#!/usr/bin/env python
# coding: utf-8

# # FEWS Network Visualization Interactive Analysis
# 
# This notebook provides tools to analyze and visualize relationships in Delft-FEWS configurations.
# It allows you to answer key questions like:
# 
# - Which time series sets influence a particular discharge computation?
# - If I change a location set, which workflows are affected?
# - How do data flow through transformation networks?

# ## 1. Setup and Configuration

# Import necessary libraries
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from pathlib import Path
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

# Set plot styling
plt.style.use('ggplot')
sns.set_theme()

# ## 2. Database Connection Functions

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def execute_query(conn, query, params=()):
    """Execute SQL query and return results as DataFrame."""
    return pd.read_sql_query(query, conn, params=params)

def list_available_databases(db_dir='db'):
    """List available databases in the db directory."""
    db_path = Path(db_dir)
    return [f.name for f in db_path.glob('*.db*') if f.is_file()]

# Example usage:
# db_list = list_available_databases()
# print("Available databases:")
# for db in db_list:
#     print(f"- {db}")
# 
# # Connect to a specific database
# conn = connect_to_db("db/fews_config.db3")

# ## 3. Core Query Functions

def find_transformation_by_name(conn, name_pattern):
    """Find transformations matching a name pattern."""
    query = """
    SELECT id, desc, mic_id 
    FROM trafos 
    WHERE desc LIKE ?
    """
    return execute_query(conn, query, ('%' + name_pattern + '%',))

def find_tss_by_parameter(conn, parameter_pattern):
    """Find time series sets matching a parameter name pattern."""
    query = """
    SELECT id, modins, vtype, parid, qualifiers, tstype, timess
    FROM ts_sets 
    WHERE parid LIKE ?
    """
    return execute_query(conn, query, ('%' + parameter_pattern + '%',))

def find_upstream_dependencies(conn, tss_id):
    """Find all transformations that produce a given time series."""
    query = """
    SELECT t.id, t.desc, t.mic_id
    FROM trafos t
    JOIN links l ON t.id = l.trafo_id
    WHERE l.tss_id = ? AND l.inout = 'out'
    """
    return execute_query(conn, query, (tss_id,))

def find_downstream_impacts(conn, tss_id):
    """Find all transformations that consume a given time series."""
    query = """
    SELECT t.id, t.desc, t.mic_id
    FROM trafos t
    JOIN links l ON t.id = l.trafo_id
    WHERE l.tss_id = ? AND l.inout = 'in'
    """
    return execute_query(conn, query, (tss_id,))

def get_tss_details(conn, tss_id):
    """Get details about a specific time series set."""
    query = """
    SELECT * 
    FROM ts_sets
    WHERE id = ?
    """
    return execute_query(conn, query, (tss_id,))

def get_transformation_details(conn, trafo_id):
    """Get details about a specific transformation."""
    query = """
    SELECT t.*, mc.modins, mc.call_stack_id
    FROM trafos t
    JOIN modins_calls mc ON t.mic_id = mc.id
    WHERE t.id = ?
    """
    return execute_query(conn, query, (trafo_id,))

# Example usage:
# transformations = find_transformation_by_name(conn, "debiet")
# print(f"Found {len(transformations)} transformations related to discharge")

# ## 4. Advanced Query Functions

def find_transformation_inputs(conn, trafo_id):
    """Find all time series sets used as inputs by a transformation."""
    query = """
    SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype
    FROM ts_sets ts
    JOIN links l ON ts.id = l.tss_id
    WHERE l.trafo_id = ? AND l.inout = 'in'
    """
    return execute_query(conn, query, (trafo_id,))

def find_transformation_outputs(conn, trafo_id):
    """Find all time series sets produced by a transformation."""
    query = """
    SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype
    FROM ts_sets ts
    JOIN links l ON ts.id = l.tss_id
    WHERE l.trafo_id = ? AND l.inout = 'out'
    """
    return execute_query(conn, query, (trafo_id,))

def trace_workflow_impact(conn, tss_id):
    """Identify all workflows affected by a time series."""
    query = """
    SELECT DISTINCT cs.id, cs.wf_id, cs.desc
    FROM call_stacks cs
    JOIN modins_calls mc ON cs.id = mc.call_stack_id
    JOIN trafos t ON mc.id = t.mic_id
    JOIN links l ON t.id = l.trafo_id
    WHERE l.tss_id = ?
    """
    return execute_query(conn, query, (tss_id,))

def get_workflow_hierarchy(conn, workflow_id):
    """Get the parent-child hierarchy for a workflow."""
    query = """
    WITH RECURSIVE workflow_tree AS (
        SELECT id, wf_id, desc, parent_id, 0 as level
        FROM call_stacks
        WHERE wf_id = ?
        UNION ALL
        SELECT cs.id, cs.wf_id, cs.desc, cs.parent_id, wt.level + 1
        FROM call_stacks cs
        JOIN workflow_tree wt ON cs.parent_id = wt.id
    )
    SELECT * FROM workflow_tree
    ORDER BY level, id
    """
    return execute_query(conn, query, (workflow_id,))

# Example usage:
# inputs = find_transformation_inputs(conn, 1)  # For transformation with ID 1
# print(f"Transformation uses {len(inputs)} time series as inputs")

# ## 5. Key Question Answering Functions

def find_discharge_inputs(conn, discharge_name):
    """
    Find all inputs that influence a discharge computation.
    
    Args:
        conn: Database connection
        discharge_name: Name pattern for the discharge transformation
        
    Returns:
        DataFrame with input time series that affect the discharge
    """
    # 1. Find the transformation(s) for the discharge computation
    trafos = find_transformation_by_name(conn, discharge_name)
    
    if trafos.empty:
        print(f"No transformations found matching '{discharge_name}'")
        return pd.DataFrame()
    
    print(f"Found {len(trafos)} transformations related to discharge '{discharge_name}':")
    print(trafos)
    
    # 2. For each transformation, find direct inputs
    all_inputs = pd.DataFrame()
    for i, row in trafos.iterrows():
        trafo_id = row['id']
        trafo_desc = row['desc']
        print(f"\nAnalyzing inputs for transformation '{trafo_desc}' (ID: {trafo_id})")
        
        inputs = find_transformation_inputs(conn, trafo_id)
        if not inputs.empty:
            inputs['source_trafo_id'] = trafo_id
            inputs['source_trafo_desc'] = trafo_desc
            all_inputs = pd.concat([all_inputs, inputs])
    
    return all_inputs

def find_affected_workflows(conn, location_pattern):
    """
    Find workflows affected by changes to a location set.
    
    Args:
        conn: Database connection
        location_pattern: Pattern to match location in parameter ID or qualifiers
        
    Returns:
        DataFrame with affected workflows
    """
    # 1. Find time series sets related to the location
    query = """
    SELECT id, modins, parid, qualifiers
    FROM ts_sets
    WHERE parid LIKE ? OR qualifiers LIKE ?
    """
    tss_list = execute_query(conn, query, 
                           ('%' + location_pattern + '%', 
                            '%' + location_pattern + '%'))
    
    if tss_list.empty:
        print(f"No time series found matching location '{location_pattern}'")
        return pd.DataFrame()
    
    print(f"Found {len(tss_list)} time series related to location '{location_pattern}':")
    print(tss_list)
    
    # 2. For each time series, find affected workflows
    all_workflows = pd.DataFrame()
    for i, row in tss_list.iterrows():
        tss_id = row['id']
        print(f"\nAnalyzing workflows affected by time series {tss_id} ({row['parid']})")
        
        workflows = trace_workflow_impact(conn, tss_id)
        if not workflows.empty:
            workflows['source_tss_id'] = tss_id
            workflows['source_parid'] = row['parid']
            all_workflows = pd.concat([all_workflows, workflows])
    
    # 3. Remove duplicates and return
    if not all_workflows.empty:
        all_workflows = all_workflows.drop_duplicates(subset=['id', 'wf_id'])
        
    return all_workflows

# Example usage:
# discharge_inputs = find_discharge_inputs(conn, "debiet")
# affected_workflows = find_affected_workflows(conn, "Halfweg")

# ## 6. Visualization Functions

def create_transformation_network(conn, trafo_id, depth=1):
    """
    Create a network representation of a transformation with its inputs and outputs.
    
    Args:
        conn: Database connection
        trafo_id: ID of the transformation to visualize
        depth: How many levels of upstream/downstream transformations to include
        
    Returns:
        NetworkX graph object representing the transformation network
    """
    G = nx.DiGraph()
    
    # Get transformation details
    trafo_details = get_transformation_details(conn, trafo_id)
    if trafo_details.empty:
        print(f"No transformation found with ID {trafo_id}")
        return G
    
    trafo_desc = trafo_details.iloc[0]['desc']
    
    # Add the central transformation node
    G.add_node(f"T{trafo_id}", id=trafo_id, label=trafo_desc, type='transformation')
    
    # Add input time series
    inputs = find_transformation_inputs(conn, trafo_id)
    for i, input_tss in inputs.iterrows():
        tss_id = input_tss['id']
        tss_label = f"{input_tss['parid']}"
        if input_tss['qualifiers']:
            tss_label += f" ({input_tss['qualifiers']})"
        
        G.add_node(f"TSS{tss_id}", id=tss_id, label=tss_label, type='timeseries')
        G.add_edge(f"TSS{tss_id}", f"T{trafo_id}")
    
    # Add output time series
    outputs = find_transformation_outputs(conn, trafo_id)
    for i, output_tss in outputs.iterrows():
        tss_id = output_tss['id']
        tss_label = f"{output_tss['parid']}"
        if output_tss['qualifiers']:
            tss_label += f" ({output_tss['qualifiers']})"
        
        G.add_node(f"TSS{tss_id}", id=tss_id, label=tss_label, type='timeseries')
        G.add_edge(f"T{trafo_id}", f"TSS{tss_id}")
    
    # Add upstream/downstream transformations if depth > 1
    if depth > 1:
        # TODO: Add recursive exploration of network
        pass
    
    return G

def visualize_transformation_network(G):
    """
    Visualize a transformation network using matplotlib.
    
    Args:
        G: NetworkX graph representing the transformation network
    """
    plt.figure(figsize=(12, 8))
    
    # Create position layout
    pos = nx.spring_layout(G, k=0.8)
    
    # Draw nodes with different colors based on type
    transformation_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'transformation']
    timeseries_nodes = [n for n, d in G.nodes(data=True) if d.get('type') == 'timeseries']
    
    nx.draw_networkx_nodes(G, pos, nodelist=transformation_nodes, node_color='lightblue', 
                         node_size=800, alpha=0.8)
    nx.draw_networkx_nodes(G, pos, nodelist=timeseries_nodes, node_color='lightgreen', 
                         node_size=600, alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrows=True)
    
    # Draw labels
    labels = {n: d.get('label', n) for n, d in G.nodes(data=True)}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    
    plt.title("Transformation Network")
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def visualize_interactive_network(G):
    """
    Create an interactive visualization of a transformation network using Plotly.
    
    Args:
        G: NetworkX graph representing the transformation network
    """
    pos = nx.spring_layout(G, dim=3, k=0.8)
    
    # Create edge traces
    edge_x = []
    edge_y = []
    edge_z = []
    
    for edge in G.edges():
        x0, y0, z0 = pos[edge[0]]
        x1, y1, z1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        edge_z.extend([z0, z1, None])
    
    edge_trace = go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines')
    
    # Create node traces for transformations and time series
    node_x = []
    node_y = []
    node_z = []
    node_text = []
    node_color = []
    node_size = []
    
    for node, attr in G.nodes(data=True):
        x, y, z = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_z.append(z)
        node_text.append(attr.get('label', node))
        
        if attr.get('type') == 'transformation':
            node_color.append('blue')
            node_size.append(10)
        else:  # timeseries
            node_color.append('green')
            node_size.append(8)
    
    node_trace = go.Scatter3d(
        x=node_x, y=node_y, z=node_z,
        mode='markers',
        marker=dict(
            size=node_size,
            color=node_color,
            line_width=2),
        text=node_text,
        hoverinfo='text')
    
    # Create figure
    fig = go.Figure(data=[edge_trace, node_trace])
    
    fig.update_layout(
        title='Interactive Transformation Network',
        scene=dict(
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False),
            zaxis=dict(showticklabels=False)
        ),
        margin=dict(b=20, l=5, r=5, t=40),
        showlegend=False
    )
    
    fig.show()

# Example usage:
# G = create_transformation_network(conn, 1)
# visualize_transformation_network(G)  # Static visualization
# visualize_interactive_network(G)     # Interactive visualization

# ## 7. Example Workflows

def analyze_discharge_computation_workflow(conn, discharge_name):
    """
    Complete workflow to analyze a discharge computation.
    
    Args:
        conn: Database connection
        discharge_name: Name of the discharge computation to analyze
    """
    print(f"=== Analysis of Discharge Computation: {discharge_name} ===\n")
    
    # 1. Find related transformations
    discharge_trafos = find_transformation_by_name(conn, discharge_name)
    
    if discharge_trafos.empty:
        print(f"No transformations found matching '{discharge_name}'")
        return
    
    print(f"Found {len(discharge_trafos)} transformations:")
    print(discharge_trafos[['id', 'desc']])
    print("\n")
    
    # 2. Select the most relevant transformation
    if len(discharge_trafos) > 1:
        print("Multiple transformations found. Using the first one for detailed analysis.")
    
    trafo_id = discharge_trafos.iloc[0]['id']
    trafo_desc = discharge_trafos.iloc[0]['desc']
    
    # 3. Create network visualization
    print(f"Creating network visualization for '{trafo_desc}'...")
    G = create_transformation_network(conn, trafo_id)
    visualize_transformation_network(G)
    
    # 4. Analyze direct inputs
    direct_inputs = find_transformation_inputs(conn, trafo_id)
    
    print(f"\nDirect inputs for transformation '{trafo_desc}':")
    if direct_inputs.empty:
        print("No direct inputs found.")
    else:
        print(direct_inputs[['id', 'modins', 'parid', 'qualifiers']])
    
    # 5. Analyze which workflows this is part of
    workflow_info = execute_query(conn, """
        SELECT cs.id, cs.wf_id, cs.desc
        FROM call_stacks cs
        JOIN modins_calls mc ON cs.id = mc.call_stack_id
        JOIN trafos t ON mc.id = t.mic_id
        WHERE t.id = ?
    """, (trafo_id,))
    
    print("\nThis discharge computation is part of the following workflows:")
    if workflow_info.empty:
        print("No workflow information found.")
    else:
        print(workflow_info[['wf_id', 'desc']])
    
    print("\n=== Analysis Complete ===")

def analyze_location_impact_workflow(conn, location_name):
    """
    Complete workflow to analyze the impact of changes to a location.
    
    Args:
        conn: Database connection
        location_name: Name of the location to analyze
    """
    print(f"=== Impact Analysis for Location: {location_name} ===\n")
    
    # 1. Find time series related to this location
    location_tss = find_tss_by_parameter(conn, location_name)
    
    if location_tss.empty:
        print(f"No time series found related to location '{location_name}'")
        return
    
    print(f"Found {len(location_tss)} time series related to location '{location_name}':")
    print(location_tss[['id', 'modins', 'parid', 'qualifiers']])
    print("\n")
    
    # 2. Find workflows affected by these time series
    affected_wfs = find_affected_workflows(conn, location_name)
    
    print(f"\nWorkflows affected by changes to location '{location_name}':")
    if affected_wfs.empty:
        print("No affected workflows found.")
    else:
        print(affected_wfs[['wf_id', 'desc']].drop_duplicates())
    
    # 3. Visual representation of the impact
    if not location_tss.empty:
        # Create a network showing how this location's data is used
        # This is a simplified version - we just use the first time series
        tss_id = location_tss.iloc[0]['id']
        
        # Find downstream transformations
        downstream = find_downstream_impacts(conn, tss_id)
        
        if not downstream.empty:
            print(f"\nTransformations directly consuming data from this location:")
            print(downstream[['id', 'desc']])
            
            # Create visualization for first downstream transformation
            trafo_id = downstream.iloc[0]['id']
            print(f"\nCreating network visualization for transformation ID {trafo_id}...")
            G = create_transformation_network(conn, trafo_id)
            visualize_transformation_network(G)
    
    print("\n=== Impact Analysis Complete ===")

# Example usage:
# analyze_discharge_computation_workflow(conn, "debiet")
# analyze_location_impact_workflow(conn, "Halfweg")

# ## 8. Utility Functions for Data Exploration

def list_available_transformations(conn, limit=20):
    """List available transformations in the database."""
    query = "SELECT id, desc FROM trafos LIMIT ?"
    return execute_query(conn, query, (limit,))

def list_available_tss(conn, limit=20):
    """List available time series sets in the database."""
    query = "SELECT id, modins, parid, qualifiers FROM ts_sets LIMIT ?"
    return execute_query(conn, query, (limit,))

def list_available_workflows(conn, limit=20):
    """List available workflows in the database."""
    query = "SELECT id, wf_id, desc FROM call_stacks LIMIT ?"
    return execute_query(conn, query, (limit,))

def export_results(df, filename):
    """Export results to CSV file."""
    df.to_csv(filename, index=False)
    print(f"Results exported to {filename}")

# Example usage:
# trafos = list_available_transformations(conn)
# print("Available transformations:")
# print(trafos)
# 
# tss = list_available_tss(conn)
# print("\nAvailable time series sets:")
# print(tss)
# 
# workflows = list_available_workflows(conn)
# print("\nAvailable workflows:")
# print(workflows)

# ## 9. Main Analysis Example
# 
# This section shows a complete example of how to use this notebook for analysis.
# Uncomment and modify the code below to run your own analysis.

# # Connect to database
# db_path = "db/fews_config.db3"
# conn = connect_to_db(db_path)
# 
# # Show available data
# print("Available transformations:")
# print(list_available_transformations(conn, 5))
# 
# print("\nAvailable time series:")
# print(list_available_tss(conn, 5))
# 
# # Example 1: Analyze a discharge computation
# analyze_discharge_computation_workflow(conn, "debiet")
# 
# # Example 2: Analyze location impact
# analyze_location_impact_workflow(conn, "Halfweg")
# 
# # Close connection
# conn.close()

# ## 10. Conclusion
# 
# This notebook provides tools to analyze and visualize FEWS configurations, helping users understand:
# 
# 1. Dependencies between time series and transformations
# 2. The impact of changes to location sets on workflows
# 3. The flow of data through transformation networks
# 
# The functions can be customized and extended to answer specific questions about your FEWS configuration. 