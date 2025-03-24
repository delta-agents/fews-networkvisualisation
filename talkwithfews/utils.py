"""
Utility functions for the FEWS Configuration Agent.

This module provides utility functions for connecting to the database and formatting results.
"""

import sqlite3
import os
from typing import List, Dict, Any


def connect_to_database(db_path: str) -> sqlite3.Connection:
    """
    Connect to the SQLite database.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        sqlite3.Connection: Connection to the database
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    connection = sqlite3.connect(db_path)
    # Enable foreign keys
    connection.execute("PRAGMA foreign_keys = ON")
    # Return rows as dictionaries
    connection.row_factory = sqlite3.Row
    
    return connection


def format_results_as_table(results: List[Dict[str, Any]], column_names: List[str]) -> str:
    """
    Format query results as a table.
    
    Args:
        results: List of dictionaries with query results
        column_names: List of column names
        
    Returns:
        str: Formatted table
    """
    if not results:
        return "No results found."
    
    # Calculate column widths
    widths = {col: len(col) for col in column_names}
    for row in results:
        for col in column_names:
            if col in row:
                widths[col] = max(widths[col], len(str(row[col])))
    
    # Format header
    header = " | ".join(col.ljust(widths[col]) for col in column_names)
    separator = "-+-".join("-" * widths[col] for col in column_names)
    
    # Format rows
    rows = []
    for row in results:
        formatted_row = " | ".join(
            str(row.get(col, "")).ljust(widths[col]) for col in column_names
        )
        rows.append(formatted_row)
    
    # Combine everything
    table = f"{header}\n{separator}\n" + "\n".join(rows)
    
    return table


def generate_mermaid_diagram(results: List[Dict[str, Any]], diagram_type: str) -> str:
    """
    Generate a Mermaid diagram based on query results.
    
    Args:
        results: List of dictionaries with query results
        diagram_type: Type of diagram to generate (flowchart, graph, etc.)
        
    Returns:
        str: Mermaid diagram code
    """
    if not results:
        return "```mermaid\ngraph LR\n  A[No results found]\n```"
    
    if diagram_type == "workflow_hierarchy":
        # Generate a workflow hierarchy diagram
        diagram = "```mermaid\nflowchart TD\n"
        
        for row in results:
            node_id = f"WF{row['id']}"
            node_label = f"{row['wf_id']}"
            
            diagram += f"  {node_id}[{node_label}]\n"
            
            if row.get('parent_id'):
                parent_id = f"WF{row['parent_id']}"
                diagram += f"  {parent_id} --> {node_id}\n"
        
        diagram += "```"
        return diagram
    
    elif diagram_type == "transformation_flow":
        # Generate a transformation flow diagram
        diagram = "```mermaid\nflowchart LR\n"
        
        for i, row in enumerate(results):
            if 'trafo_id' in row and 'tss_id' in row:
                trafo_id = f"T{row['trafo_id']}"
                tss_id = f"TS{row['tss_id']}"
                
                trafo_label = row.get('trafo_desc', f"Transformation {row['trafo_id']}")
                tss_label = row.get('parid', f"TimeSeries {row['tss_id']}")
                
                diagram += f"  {trafo_id}[{trafo_label}]\n"
                diagram += f"  {tss_id}[{tss_label}]\n"
                
                if row.get('inout') == 'in':
                    diagram += f"  {tss_id} --> {trafo_id}\n"
                else:
                    diagram += f"  {trafo_id} --> {tss_id}\n"
        
        diagram += "```"
        return diagram
    
    else:
        # Default to a simple graph
        diagram = "```mermaid\ngraph LR\n"
        
        for i, row in enumerate(results):
            node_id = f"N{i}"
            node_label = ", ".join(f"{k}: {v}" for k, v in row.items() if k in ['id', 'desc', 'wf_id', 'parid'])
            
            diagram += f"  {node_id}[{node_label}]\n"
        
        diagram += "```"
        return diagram 