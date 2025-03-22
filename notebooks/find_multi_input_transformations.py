#!/usr/bin/env python
# coding: utf-8

import sqlite3
import pandas as pd
from pathlib import Path

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def find_transformations_with_multiple_inputs(db_path):
    """Find all transformations that use more than one time series as input."""
    conn = connect_to_db(db_path)
    
    # Query to find transformations with multiple inputs
    query = """
    SELECT t.id, t.desc, COUNT(l.tss_id) as input_count
    FROM trafos t
    JOIN links l ON t.id = l.trafo_id
    WHERE l.inout = 'in'
    GROUP BY t.id
    HAVING COUNT(l.tss_id) > 1
    ORDER BY input_count DESC
    """
    
    result = pd.read_sql_query(query, conn)
    
    # For each transformation with multiple inputs, get the input time series details
    detailed_results = []
    
    for _, row in result.iterrows():
        trafo_id = row['id']
        trafo_desc = row['desc']
        input_count = row['input_count']
        
        # Get details about the transformation
        trafo_details_query = """
        SELECT t.*, mc.modins
        FROM trafos t
        JOIN modins_calls mc ON t.mic_id = mc.id
        WHERE t.id = ?
        """
        trafo_details = pd.read_sql_query(trafo_details_query, conn, params=(trafo_id,))
        
        # Get input time series
        input_tss_query = """
        SELECT ts.*
        FROM ts_sets ts
        JOIN links l ON ts.id = l.tss_id
        WHERE l.trafo_id = ? AND l.inout = 'in'
        """
        input_tss = pd.read_sql_query(input_tss_query, conn, params=(trafo_id,))
        
        detailed_results.append({
            'trafo_id': trafo_id,
            'trafo_desc': trafo_desc,
            'module_instance': trafo_details.iloc[0]['modins'] if not trafo_details.empty else 'Unknown',
            'input_count': input_count,
            'input_tss': input_tss
        })
    
    conn.close()
    return result, detailed_results

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
    
    print(f"Analyzing database: {db_path}")
    summary, details = find_transformations_with_multiple_inputs(db_path)
    
    # Display summary information
    print(f"\nFound {len(summary)} transformations with multiple inputs:")
    print(summary)
    
    # Display detailed information for a few transformations
    num_to_show = min(5, len(details))
    print(f"\nDetailed information for top {num_to_show} transformations with most inputs:")
    
    for i in range(num_to_show):
        detail = details[i]
        print(f"\nTransformation {detail['trafo_id']}: {detail['trafo_desc']}")
        print(f"Module Instance: {detail['module_instance']}")
        print(f"Number of inputs: {detail['input_count']}")
        print("Input Time Series:")
        
        for j, tss in detail['input_tss'].iterrows():
            print(f"  - TSS ID: {tss['id']}, Parameter: {tss['parid']}, " +
                  f"Qualifiers: {tss['qualifiers']}, Module: {tss['modins']}")

if __name__ == "__main__":
    main() 