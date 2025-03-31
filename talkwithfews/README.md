# talkwithfews

A tool for interactive exploration of FEWS configurations through natural language.

## Overview

The `talkwithfews` package provides an agent-based interface for querying and analyzing Delft-FEWS configurations stored in a SQLite database. It allows users to ask questions in natural language and get detailed responses about workflows, time series, transformations, and their relationships.

## Module Structure

- `talkwithfews/agent.py`: Core agent implementation
- `talkwithfews/models.py`: Pydantic models for input/output
- `talkwithfews/tools.py`: Tool implementations for agent functionality 
- `talkwithfews/utils.py`: Utility functions
- `talkwithfews/logging_utils.py`: Logging infrastructure
- `talkwithfews/visualization.py`: Visualization generation tools

## Main Components

### FEWSConfigAgent

The core class that encapsulates the agent and database connection management.

```python
from talkwithfews.agent import FEWSConfigAgent

async with FEWSConfigAgent(db_path="path/to/database.db", api_key="your-api-key") as agent:
    response = await agent.ask("What workflows are in the system?")
    print(response)
```

### Tools

The agent has access to the following tools:

- `execute_query`: Executes SQL queries against the database
- `explain_query`: Explains a SQL query without executing it
- `search_workflows`: Searches for workflows by name or description
- `get_workflow_details`: Gets details for a specific workflow
- `search_timeseries`: Searches for time series by various attributes
- `get_timeseries_details`: Gets details for a specific time series
- `search_transformations`: Searches for transformations
- `get_transformation_details`: Gets details for a specific transformation
- `analyze_upstream_dependencies`: Analyzes what produces a specific entity
- `analyze_downstream_dependencies`: Analyzes what consumes a specific entity
- `find_workflow_call_hierarchy`: Analyzes workflow call stacks
- `get_database_schema`: Retrieves database schema information
- Visualization tools for generating network, call hierarchy, and data flow diagrams

## Configuration Options

The `FEWSConfigAgent` class accepts the following parameters:

- `db_path`: Path to the SQLite database
- `model`: Model to use (default: "gpt-4")
- `api_key`: API key for the model provider
- `base_url`: Base URL for the API (useful for OpenRouter)
- `log_level`: Logging level (default: "INFO")
- `log_dir`: Directory to store log files 