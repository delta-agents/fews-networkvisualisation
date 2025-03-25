"""
Logging utilities for the FEWS Configuration Agent.

This module defines logging tools used throughout the codebase.
"""

import logging
import json
from functools import wraps
from typing import TypeVar, Callable, Any, cast
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fews_agent")

# Type variable for the decorator
F = TypeVar('F', bound=Callable[..., Any])

def format_sql_query(query):
    """Format a SQL query with proper indentation."""
    # Clean up the query
    query = query.strip()
    query = " ".join(query.split())
    
    # Format with proper indentation
    formatted = query.replace("SELECT", "\nSELECT")
    formatted = formatted.replace("FROM", "\nFROM")
    formatted = formatted.replace("WHERE", "\nWHERE")
    formatted = formatted.replace("JOIN", "\nJOIN")
    formatted = formatted.replace("AND", "\nAND")
    formatted = formatted.replace("ORDER BY", "\nORDER BY")
    formatted = formatted.replace("GROUP BY", "\nGROUP BY")
    
    # Format IN clauses with long lists of values
    if "IN (" in formatted:
        parts = formatted.split("IN (")
        if len(parts) > 1:
            values_part = parts[1].split(")", 1)
            if len(values_part) > 1:
                values = [v.strip() for v in values_part[0].split(",")]
                if len(values) > 5:
                    chunks = [values[i:i+5] for i in range(0, len(values), 5)]
                    formatted_values = ",\n    ".join(", ".join(chunk) for chunk in chunks)
                    formatted = parts[0] + "IN (\n    " + formatted_values + "\n)" + values_part[1]
    
    # Format comments
    formatted = formatted.replace("--", "\n--")
    return formatted

def format_input_for_logging(input_data):
    """Format input data for logging in a readable way."""
    try:
        if hasattr(input_data, "__dict__"):
            # Convert Pydantic model to dict
            data = input_data.dict() if hasattr(input_data, "dict") else vars(input_data)
            return json.dumps(data, default=str, indent=2)
        elif isinstance(input_data, dict):
            return json.dumps(input_data, default=str, indent=2)
        else:
            return str(input_data)
    except Exception as e:
        return f"<Error formatting input: {e}>"

def log_tool_call(func: F) -> F:
    """
    Decorator to log tool calls, including inputs, outputs, and any errors.
    """
    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        tool_name = getattr(func, "__name__", str(func))
        input_data = args[0] if args else kwargs
        
        # Log the call
        logger.info(f"Calling tool: {tool_name}")
        
        # Format and log the input
        if isinstance(input_data, dict) and "query" in input_data:
            # For SQL queries in dict format
            query = input_data["query"]
            formatted_query = format_sql_query(query)
            logger.info(formatted_query)
        elif hasattr(input_data, "query"):
            # For SQLQueryInput objects
            query = input_data.query
            formatted_query = format_sql_query(query)
            logger.info(formatted_query)
        elif isinstance(input_data, dict) and "input" in input_data and not input_data["input"]:
            # Skip logging empty input dicts
            pass
        elif isinstance(input_data, dict):
            # Format other dict inputs
            formatted_input = format_input_for_logging(input_data)
            logger.info(formatted_input)
        else:
            # Format non-dict inputs
            logger.info(str(input_data))
        
        try:
            # Execute the tool
            result = await func(ctx, *args, **kwargs)
            logger.info(f"Tool {tool_name} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {str(e)}")
            raise
            
    return cast(F, wrapper)

def setup_logging(log_level="INFO", log_dir=None):
    """Set up logging configuration."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    log_file = None
    if log_dir:
        # Create log directory if it doesn't exist
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Create log file
        log_file = log_path / f"fews_agent.log"
        
        # Clear the log file if it already exists
        if log_file.exists():
            logger.info(f"Clearing existing log file: {log_file}")
            with open(log_file, 'w') as f:
                f.truncate(0)
        
        # Configure file handler with basic formatter
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(numeric_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        logger.info(f"Logging initialized. Log file: {log_file}")
    
    logger.setLevel(numeric_level)
    return log_file 