"""
Schema utilities for the FEWS Configuration Agent.

This module provides functions for extracting and formatting database schema information
in a way that is optimized for use with LLMs.
"""

import sqlite3
import re
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("fews_agent")


def diagnose_sql_error(error_message: str, query: str, schema_info: Dict[str, List[str]]) -> Optional[str]:
    """
    Diagnose common SQL errors and provide helpful suggestions.
    
    Args:
        error_message: The error message from SQLite
        query: The query that caused the error
        schema_info: Information about the database schema
        
    Returns:
        Optional[str]: A helpful suggestion or None
    """
    # Check for no such column errors
    if "no such column" in error_message:
        # Extract the column name from the error
        match = re.search(r"no such column: ([^\s]+)", error_message)
        if match and match.group(1):
            problematic_column = match.group(1)
            
            # Check if it's a column name issue with common aliases
            column_suggestions = []
            
            # Common column name mappings in FEWS database
            column_mappings = {
                "ts_set_id": ["tss_id", "id"],
                "timeseries_id": ["tss_id", "id"],
                "link_type": ["inout"],
                "parameter_id": ["parid"],
                "qualifier": ["qualifiers"],
                "module_instance": ["modins"]
            }
            
            # Check if the problematic column is one we know about
            if problematic_column in column_mappings:
                for suggestion in column_mappings[problematic_column]:
                    # Only suggest columns that exist in at least one table
                    if any(suggestion in columns for columns in schema_info.values()):
                        column_suggestions.append(suggestion)
            
            # If we have suggestions, provide them
            if column_suggestions:
                return f"Column '{problematic_column}' doesn't exist. Try using {', '.join(column_suggestions)} instead."
            
            # If no direct mapping, suggest possible columns from schema
            for table, columns in schema_info.items():
                similar_columns = [col for col in columns if problematic_column.lower() in col.lower()]
                if similar_columns:
                    return f"Column '{problematic_column}' doesn't exist in '{table}'. Available similar columns: {', '.join(similar_columns)}"
    
    # Check for no such table
    if "no such table" in error_message:
        match = re.search(r"no such table: ([^\s]+)", error_message)
        if match and match.group(1):
            problematic_table = match.group(1)
            return f"Table '{problematic_table}' doesn't exist. Available tables: {', '.join(schema_info.keys())}"
    
    return None


def extract_llm_friendly_schema(db_path: str) -> Dict[str, Any]:
    """
    Extract schema information from SQLite database in a format optimized for LLMs.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dict[str, Any]: Database schema information including tables, columns, relationships, and sample data
    """
    logger.info(f"Extracting LLM-friendly schema from database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Get list of all tables
    tables_query = """
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    ORDER BY name;
    """
    
    cursor = conn.cursor()
    cursor.execute(tables_query)
    tables = [row[0] for row in cursor.fetchall()]
    logger.info(f"Found {len(tables)} tables in the database")
    
    # Dictionary to store schema information
    schema = {
        "tables": [],
        "relationships": []
    }
    
    relationship_tracking = []  # To track relationships for later processing
    
    # Get column information for each table
    for table_name in tables:
        table_info = {
            "name": table_name,
            "columns": []
        }
        
        try:
            # Get column information
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            for column in columns:
                col_info = {
                    "name": column[1],  # column name
                    "type": column[2],  # data type
                    "primary_key": bool(column[5]),  # is primary key
                    "nullable": not bool(column[3]),  # is nullable
                    "default": column[4]  # default value
                }
                table_info["columns"].append(col_info)
            
            # Get foreign key information
            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            foreign_keys = cursor.fetchall()
            
            for fk in foreign_keys:
                relationship = {
                    "from_table": table_name,
                    "from_column": fk[3],  # from column
                    "to_table": fk[2],    # referenced table
                    "to_column": fk[4]     # referenced column
                }
                relationship_tracking.append(relationship)
            
            schema["tables"].append(table_info)
            logger.debug(f"Processed schema for table {table_name} with {len(table_info['columns'])} columns")
            
        except sqlite3.Error as e:
            logger.warning(f"Error extracting schema for table {table_name}: {str(e)}")
    
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
    
    # Add well-known FEWS relationships if none were found from database
    if not schema["relationships"]:
        logger.info("No relationships found in database, adding known FEWS relationships")
        known_relationships = [
            {"from_table": "call_stacks", "from_column": "parent_id", "to_table": "call_stacks", "to_column": "id", "relationship_type": "many-to-one"},
            {"from_table": "modins_calls", "from_column": "call_stack_id", "to_table": "call_stacks", "to_column": "id", "relationship_type": "many-to-one"},
            {"from_table": "trafos", "from_column": "mic_id", "to_table": "modins_calls", "to_column": "id", "relationship_type": "many-to-one"},
            {"from_table": "links", "from_column": "trafo_id", "to_table": "trafos", "to_column": "id", "relationship_type": "many-to-one"},
            {"from_table": "links", "from_column": "tss_id", "to_table": "ts_sets", "to_column": "id", "relationship_type": "many-to-one"},
            {"from_table": "endpoints", "from_column": "tss_id", "to_table": "ts_sets", "to_column": "id", "relationship_type": "many-to-one"}
        ]
        schema["relationships"].extend(known_relationships)
    
    # Sample data for each table (optional but can help LLMs understand data patterns)
    schema["sample_data"] = {}
    for table_name in tables:
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            if rows:
                sample_data = []
                for row in rows:
                    sample_data.append(dict(zip(columns, row)))
                schema["sample_data"][table_name] = sample_data
                
        except sqlite3.Error as e:
            logger.warning(f"Error getting sample data for {table_name}: {str(e)}")
    
    conn.close()
    logger.info(f"Extracted schema with {len(schema['tables'])} tables and {len(schema['relationships'])} relationships")
    return schema


def generate_llm_context(schema: Dict[str, Any]) -> str:
    """
    Generate a text description of the schema that's optimized for LLM context.
    This creates a clear, structured description that an LLM can easily use to generate SQL.
    
    Args:
        schema: Database schema information from extract_llm_friendly_schema
        
    Returns:
        str: Markdown-formatted description of the database schema
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
    
    # Add examples specific to FEWS configuration
    context += "## Common FEWS Queries\n\n"
    
    context += "### Find workflows by name pattern\n\n"
    context += "```sql\n"
    context += "SELECT id, wf_id, desc, wffn\n"
    context += "FROM call_stacks\n"
    context += "WHERE wf_id LIKE '%pattern%' OR desc LIKE '%pattern%'\n"
    context += "ORDER BY wf_id\n"
    context += "```\n\n"
    
    context += "### Find time series sets by parameter ID\n\n"
    context += "```sql\n"
    context += "SELECT id, modins, vtype, parid, qualifiers, tstype, timess\n"
    context += "FROM ts_sets\n"
    context += "WHERE parid LIKE '%parameter%'\n"
    context += "ORDER BY id\n"
    context += "```\n\n"
    
    context += "### Find transformations that use a specific time series\n\n"
    context += "```sql\n"
    context += "SELECT t.id, t.desc, t.mic_id, mc.modins\n"
    context += "FROM trafos t\n"
    context += "JOIN links l ON t.id = l.trafo_id\n"
    context += "JOIN modins_calls mc ON t.mic_id = mc.id\n"
    context += "WHERE l.tss_id = [time_series_id] AND l.inout = 'in'\n"
    context += "```\n\n"
    
    # Column name mappings specific to FEWS
    context += "## Column Name Mappings\n\n"
    context += "When writing queries, be aware of these column name conventions:\n\n"
    context += "- Time series IDs: Use `id` in `ts_sets` table and `tss_id` in `links` table\n"
    context += "- Link direction: Use `inout` column in `links` table with values 'in' or 'out'\n"
    context += "- Parameter IDs: Use `parid` (not parameter_id)\n"
    context += "- Qualifiers: Use `qualifiers` (not qualifier)\n"
    context += "- Module instances: Use `modins` (not module_instance)\n\n"
    
    return context


def create_schema_info_dict(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Create a simplified schema_info dictionary from the comprehensive schema.
    
    Args:
        schema: Database schema information from extract_llm_friendly_schema
        
    Returns:
        Dict[str, List[str]]: Simplified schema info with table names as keys and column lists as values
    """
    schema_info = {}
    for table in schema["tables"]:
        schema_info[table["name"]] = [col["name"] for col in table["columns"]]
    return schema_info


def get_table_relationships(schema: Dict[str, Any]) -> List[str]:
    """
    Extract table relationships from the schema in a formatted list.
    
    Args:
        schema: Database schema information from extract_llm_friendly_schema
        
    Returns:
        List[str]: Formatted table relationship strings
    """
    relationships = []
    for rel in schema["relationships"]:
        relationships.append(
            f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}"
        )
    return relationships 