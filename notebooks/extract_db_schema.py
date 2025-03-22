#!/usr/bin/env python
# coding: utf-8

import sqlite3
import pandas as pd
from pathlib import Path

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def extract_schema(db_path):
    """Extract schema information from SQLite database."""
    conn = connect_to_db(db_path)
    
    # Get list of all tables
    tables_query = """
    SELECT name FROM sqlite_master 
    WHERE type='table' 
    ORDER BY name;
    """
    
    tables = pd.read_sql_query(tables_query, conn)
    
    # Dictionary to store schema information
    schema_info = {}
    
    # Get column information for each table
    for table_name in tables['name']:
        column_info_query = f"PRAGMA table_info({table_name});"
        columns = pd.read_sql_query(column_info_query, conn)
        
        # Get foreign key information
        fk_query = f"PRAGMA foreign_key_list({table_name});"
        foreign_keys = pd.read_sql_query(fk_query, conn)
        
        # Get index information
        index_query = f"""
        SELECT name, sql FROM sqlite_master 
        WHERE type='index' AND tbl_name='{table_name}'
        """
        indexes = pd.read_sql_query(index_query, conn)
        
        schema_info[table_name] = {
            'columns': columns,
            'foreign_keys': foreign_keys,
            'indexes': indexes
        }
    
    # Get CREATE TABLE statements
    create_statements = pd.read_sql_query(
        "SELECT name, sql FROM sqlite_master WHERE type='table'", 
        conn
    )
    
    conn.close()
    return schema_info, create_statements

def print_schema(schema_info, create_statements):
    """Print schema information in a readable format."""
    print("=== DATABASE SCHEMA ===\n")
    
    # Print each table and its columns
    for table_name, info in schema_info.items():
        print(f"TABLE: {table_name}")
        print("-" * 80)
        
        # Print columns
        print("COLUMNS:")
        columns_df = info['columns']
        print(columns_df.to_string(index=False))
        print()
        
        # Print foreign keys if any
        if not info['foreign_keys'].empty:
            print("FOREIGN KEYS:")
            fk_df = info['foreign_keys']
            print(fk_df.to_string(index=False))
            print()
        
        # Print indexes if any
        if not info['indexes'].empty:
            print("INDEXES:")
            idx_df = info['indexes']
            print(idx_df.to_string(index=False))
            print()
        
        # Print CREATE TABLE statement
        create_sql = create_statements[create_statements['name'] == table_name]['sql'].values[0]
        print("CREATE TABLE STATEMENT:")
        print(create_sql)
        print("\n" + "=" * 80 + "\n")

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
    
    print(f"Extracting schema from database: {db_path}")
    schema_info, create_statements = extract_schema(db_path)
    
    # Print summary information
    table_count = len(schema_info)
    print(f"\nDatabase contains {table_count} tables:")
    for table_name in schema_info.keys():
        column_count = len(schema_info[table_name]['columns'])
        print(f"  - {table_name}: {column_count} columns")
    
    # Ask if user wants to see detailed schema
    detailed_view = input("\nShow detailed schema? (y/n): ")
    if detailed_view.lower() in ('y', 'yes'):
        print_schema(schema_info, create_statements)
    
    # Alternatively, save schema to a file
    save_to_file = input("\nSave schema to file? (y/n): ")
    if save_to_file.lower() in ('y', 'yes'):
        output_file = f"{Path(db_path).stem}_schema.txt"
        with open(output_file, 'w') as f:
            # Redirect print output to file
            import sys
            original_stdout = sys.stdout
            sys.stdout = f
            print_schema(schema_info, create_statements)
            sys.stdout = original_stdout
        print(f"Schema saved to {output_file}")

if __name__ == "__main__":
    main() 