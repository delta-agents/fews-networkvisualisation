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
        
        # Log the call with input details
        formatted_input = format_input_for_logging(input_data)
        logger.info(f"Calling tool: {tool_name}")
        logger.info(f"Tool input: {formatted_input}")
        
        # Check if reasoning was provided
        if hasattr(ctx.deps, 'tracker') and ctx.deps.tracker is not None:
            reasoning = getattr(ctx.deps.tracker, 'current_reasoning', None)
            if reasoning:
                logger.info(f"Reasoning: {reasoning}")
        
        try:
            # Execute the tool
            result = await func(ctx, *args, **kwargs)
            
            # Log successful result
            logger.info(f"Tool {tool_name} completed successfully")
            
            # Track the call if tracker is available in deps
            if hasattr(ctx.deps, 'tracker') and ctx.deps.tracker is not None:
                ctx.deps.tracker.log_call(tool_name, input_data, result)
                
            return result
            
        except Exception as e:
            # Log error
            logger.error(f"Tool {tool_name} failed: {str(e)}")
            
            # Track the error
            if hasattr(ctx.deps, 'tracker') and ctx.deps.tracker is not None:
                ctx.deps.tracker.log_call(tool_name, input_data, None, str(e))
                
            # Re-raise the exception
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
        
        # Create timestamped log file
        #from datetime import datetime
        #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        #log_file = log_path / f"fews_agent_{timestamp}.log"
        log_file = log_path / f"fews_agent.log"
        
        # Clear the log file if it already exists
        if log_file.exists():
            logger.info(f"Clearing existing log file: {log_file}")
            with open(log_file, 'w') as f:
                f.truncate(0)
        
        # Configure file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        logger.info(f"Logging initialized. Log file: {log_file}")
    
    logger.setLevel(numeric_level)
    return log_file 