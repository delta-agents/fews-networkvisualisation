#!/usr/bin/env python
# coding: utf-8

import sqlite3
import pandas as pd
import json
from pathlib import Path

def connect_to_db(db_path):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def extract_llm_friendly_schema(db_path):
    """Extract schema information from SQLite database in a format optimized for LLMs."""
    conn = connect_to_db(db_path)
    
    # Get list of all tables
    tables_query = """
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    ORDER BY name;
    """
    
    tables = pd.read_sql_query(tables_query, conn)
    
    # Dictionary to store schema information
    schema = {
        "tables": [],
        "relationships": []
    }
    
    relationship_tracking = []  # To track relationships for later processing
    
    # Get column information for each table
    for table_name in tables['name']:
        table_info = {
            "name": table_name,
            "columns": []
        }
        
        # Get column information
        column_info_query = f"PRAGMA table_info({table_name});"
        columns = pd.read_sql_query(column_info_query, conn)
        
        for _, column in columns.iterrows():
            col_info = {
                "name": column['name'],
                "type": column['type'],
                "primary_key": bool(column['pk']),
                "nullable": not bool(column['notnull']),
                "default": column['dflt_value']
            }
            table_info["columns"].append(col_info)
        
        # Get foreign key information
        fk_query = f"PRAGMA foreign_key_list({table_name});"
        foreign_keys = pd.read_sql_query(fk_query, conn)
        
        for _, fk in foreign_keys.iterrows():
            relationship = {
                "from_table": table_name,
                "from_column": fk['from'],
                "to_table": fk['table'],
                "to_column": fk['to']
            }
            relationship_tracking.append(relationship)
        
        schema["tables"].append(table_info)
    
    # Process relationships
    for rel in relationship_tracking:
        relationship_info = {
            "from_table": rel["from_table"],
            "from_column": rel["from_column"],
            "to_table": rel["to_table"],
            "to_column": rel["to_column"],
            "relationship_type": "many-to-one"  # Assuming most FK relationships are many-to-one
        }
        schema["relationships"].append(relationship_info)
    
    # Sample data for each table (optional but can help LLMs understand data patterns)
    schema["sample_data"] = {}
    for table_name in tables['name']:
        try:
            sample_query = f"SELECT * FROM {table_name} LIMIT 3;"
            sample_data = pd.read_sql_query(sample_query, conn)
            schema["sample_data"][table_name] = sample_data.to_dict(orient='records')
        except:
            # Skip if we can't get sample data
            pass
    
    conn.close()
    return schema

def generate_llm_context(schema):
    """
    Generate a text description of the schema that's optimized for LLM context.
    This creates a clear, structured description that an LLM can easily use to generate SQL.
    """
    context = "# Database Schema\n\n"
    
    # Describe tables and their columns
    context += "## Tables\n\n"
    for table in schema["tables"]:
        context += f"### {table['name']}\n\n"
        context += "| Column | Type | Constraints | Description |\n"
        context += "|--------|------|-------------|-------------|\n"
        
        for col in table["columns"]:
            constraints = []
            if col["primary_key"]:
                constraints.append("PRIMARY KEY")
            if not col["nullable"]:
                constraints.append("NOT NULL")
            if col["default"] is not None:
                constraints.append(f"DEFAULT {col['default']}")
                
            constraint_str = ", ".join(constraints)
            # We don't have column descriptions in the schema extraction, so leaving blank
            context += f"| {col['name']} | {col['type']} | {constraint_str} | |\n"
        
        context += "\n"
    
    # Describe relationships
    if schema["relationships"]:
        context += "## Relationships\n\n"
        for rel in schema["relationships"]:
            context += f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']} ({rel['relationship_type']})\n"
        
        context += "\n"
    
    # Add sample queries section to help the LLM understand how to use the schema
    context += "## Sample Queries\n\n"
    
    # For tables with relationships, create sample join queries
    if schema["relationships"]:
        rel = schema["relationships"][0]  # Use the first relationship as an example
        context += f"### Query with a join between {rel['from_table']} and {rel['to_table']}\n\n"
        context += "```sql\n"
        context += f"SELECT *\n"
        context += f"FROM {rel['from_table']}\n"
        context += f"JOIN {rel['to_table']} ON {rel['from_table']}.{rel['from_column']} = {rel['to_table']}.{rel['to_column']}\n"
        context += "```\n\n"
    
    # Add instructions for the LLM
    context += "## Instructions for SQL Generation\n\n"
    context += "When generating SQL queries based on user questions:\n\n"
    context += "1. Identify the tables and columns relevant to the question\n"
    context += "2. Use appropriate joins when information from multiple tables is needed\n"
    context += "3. Include necessary WHERE clauses to filter the data as specified in the question\n"
    context += "4. Use appropriate aggregation functions (COUNT, SUM, AVG, etc.) when summary information is requested\n"
    context += "5. Format the SQL query to be readable with proper indentation\n"
    
    return context

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
    
    print(f"Extracting LLM-friendly schema from database: {db_path}")
    schema = extract_llm_friendly_schema(db_path)
    
    # Print summary information
    table_count = len(schema["tables"])
    relationship_count = len(schema["relationships"])
    print(f"\nDatabase contains {table_count} tables and {relationship_count} relationships")
    
    # Generate the LLM-friendly context
    llm_context = generate_llm_context(schema)
    
    # Save to files
    db_name = Path(db_path).stem
    
    # Save raw schema as JSON
    json_file = f"{db_name}_llm_schema.json"
    with open(json_file, 'w') as f:
        json.dump(schema, f, indent=2)
    print(f"Schema JSON saved to {json_file}")
    
    # Save LLM-friendly context as markdown
    md_file = f"{db_name}_llm_context.md"
    with open(md_file, 'w') as f:
        f.write(llm_context)
    print(f"LLM context markdown saved to {md_file}")
    
    # Print a preview of the LLM context
    print("\nPreview of LLM-friendly context:")
    print("=" * 80)
    print(llm_context[:500] + "...\n")
    print("=" * 80)
    print(f"Full context available in {md_file}")

if __name__ == "__main__":
    main() 