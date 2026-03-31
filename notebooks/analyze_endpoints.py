#!/usr/bin/env python
# coding: utf-8

"""
FEWS Configuration Endpoints Analyzer

This script identifies and analyzes the endpoints (final outputs) in a FEWS configuration.
Endpoints represent the terminal nodes in the FEWS data flow network.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import networkx as nx
from pathlib import Path
import seaborn as sns

# Set plot styling
plt.style.use('ggplot')
sns.set_theme()

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def find_endpoints(conn):
    """
    Find all endpoints (final outputs) in the FEWS configuration.
    
    Args:
        conn: Database connection
        
    Returns:
        DataFrame with endpoint information
    """
    query = """
    SELECT e.tss_id, e.desc, ts.parid, ts.qualifiers, ts.modins, ts.tstype, ts.timess
    FROM endpoints e
    JOIN ts_sets ts ON e.tss_id = ts.id
    ORDER BY ts.parid
    """
    
    return pd.read_sql_query(query, conn)

def find_endpoint_sources(conn, endpoint_tss_id):
    """
    Find transformations that produce a specific endpoint.
    
    Args:
        conn: Database connection
        endpoint_tss_id: The time series set ID of the endpoint
        
    Returns:
        DataFrame with transformation information
    """
    query = """
    SELECT t.idx, t.description, m.modins, c.wf_id, c.desc as workflow_desc
    FROM trafos t
    JOIN links l ON t.idx = l.trafo_idx
    JOIN modins_calls m ON t.mic_id = m.id
    JOIN call_stacks c ON m.call_stack_id = c.id
    WHERE l.tss_id = ? AND l.inout = 'out'
    """
    
    return pd.read_sql_query(query, conn, params=(endpoint_tss_id,))

def analyze_endpoints_by_type(endpoints_df):
    """
    Analyze endpoints by their time series type.
    
    Args:
        endpoints_df: DataFrame with endpoint information
        
    Returns:
        DataFrame with counts by type
    """
    return endpoints_df.groupby('tstype').size().reset_index(name='count').sort_values('count', ascending=False)

def analyze_endpoints_by_module(endpoints_df):
    """
    Analyze endpoints by their module instance.
    
    Args:
        endpoints_df: DataFrame with endpoint information
        
    Returns:
        DataFrame with counts by module
    """
    return endpoints_df.groupby('modins').size().reset_index(name='count').sort_values('count', ascending=False)

def visualize_endpoint_types(endpoints_by_type):
    """Visualize the distribution of endpoint types."""
    plt.figure(figsize=(12, 6))
    
    # Create a bar chart
    ax = sns.barplot(x='tstype', y='count', data=endpoints_by_type)
    
    # Customize the plot
    plt.title('Distribution of Endpoint Types')
    plt.xlabel('Time Series Type')
    plt.ylabel('Count')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Add count labels on top of bars
    for i, v in enumerate(endpoints_by_type['count']):
        ax.text(i, v + 0.1, str(v), ha='center')
    
    plt.show()

def visualize_endpoint_modules(endpoints_by_module, top_n=10):
    """Visualize the distribution of endpoint module instances."""
    # Get the top N modules by count
    top_modules = endpoints_by_module.head(top_n)
    
    plt.figure(figsize=(12, 6))
    
    # Create a bar chart
    ax = sns.barplot(x='modins', y='count', data=top_modules)
    
    # Customize the plot
    plt.title(f'Top {top_n} Module Instances by Endpoint Count')
    plt.xlabel('Module Instance')
    plt.ylabel('Count')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    # Add count labels on top of bars
    for i, v in enumerate(top_modules['count']):
        ax.text(i, v + 0.1, str(v), ha='center')
    
    plt.show()

def generate_endpoint_report(endpoints_df, conn):
    """
    Generate a detailed report about endpoints.
    
    Args:
        endpoints_df: DataFrame with endpoint information
        conn: Database connection
    """
    # Overall statistics
    total_endpoints = len(endpoints_df)
    unique_parameters = endpoints_df['parid'].nunique()
    
    print(f"=== FEWS Configuration Endpoints Analysis ===\n")
    print(f"Total number of endpoints: {total_endpoints}")
    print(f"Number of unique parameters: {unique_parameters}")
    
    # Display endpoint types distribution
    endpoints_by_type = analyze_endpoints_by_type(endpoints_df)
    print("\nEndpoint Types Distribution:")
    print(endpoints_by_type.to_string(index=False))
    
    # Display endpoint modules distribution
    endpoints_by_module = analyze_endpoints_by_module(endpoints_df)
    print("\nTop 10 Module Instances by Endpoint Count:")
    print(endpoints_by_module.head(10).to_string(index=False))
    
    # Show some example endpoints
    print("\nSample Endpoints:")
    sample_endpoints = endpoints_df.sample(min(5, len(endpoints_df)))
    for _, endpoint in sample_endpoints.iterrows():
        print(f"\nEndpoint TSS ID: {endpoint['tss_id']}")
        print(f"  Description: {endpoint['desc']}")
        print(f"  Parameter: {endpoint['parid']}")
        print(f"  Qualifiers: {endpoint['qualifiers']}")
        print(f"  Module: {endpoint['modins']}")
        print(f"  Type: {endpoint['tstype']}")
        print(f"  Time Step: {endpoint['timess']}")
        
        # Find the transformations that produce this endpoint
        sources = find_endpoint_sources(conn, endpoint['tss_id'])
        if not sources.empty:
            print("  Produced by transformations:")
            for _, source in sources.iterrows():
                print(f"    - {source['desc']} (ID: {source['id']}) in workflow: {source['workflow_desc']}")
        else:
            print("  No producing transformations found")
    
    print("\n=== Analysis Complete ===")

def main():
    # Use the Rijnland config database from the earlier examples
    db_path = "../db/fews_config.db3"
    
    if not Path(db_path).exists():
        print(f"Database file not found: {db_path}")
        available_dbs = list(Path("../db").glob("*.db*"))
        if available_dbs:
            print("Available databases:")
            for db in available_dbs:
                print(f" - {db}")
            db_path = str(available_dbs[0])
            print(f"Using first available database: {db_path}")
        else:
            print("No database files found in the db directory.")
            return
    
    print(f"Analyzing endpoints in database: {db_path}")
    
    try:
        # Connect to the database
        conn = connect_to_db(db_path)
        
        # Find endpoints
        endpoints_df = find_endpoints(conn)
        
        if endpoints_df.empty:
            print("No endpoints found in the database.")
            return
        
        # Generate endpoint report
        generate_endpoint_report(endpoints_df, conn)
        
        # Visualize endpoint statistics
        endpoints_by_type = analyze_endpoints_by_type(endpoints_df)
        visualize_endpoint_types(endpoints_by_type)
        
        endpoints_by_module = analyze_endpoints_by_module(endpoints_df)
        visualize_endpoint_modules(endpoints_by_module)
        
        # Optional: Export endpoints to CSV
        save_to_csv = input("\nSave endpoints to CSV file? (y/n): ")
        if save_to_csv.lower() in ('y', 'yes'):
            csv_file = f"{Path(db_path).stem}_endpoints.csv"
            endpoints_df.to_csv(csv_file, index=False)
            print(f"Endpoints saved to {csv_file}")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        # Close the connection
        if conn:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    main() 