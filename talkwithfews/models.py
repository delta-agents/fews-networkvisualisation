"""
Pydantic models for the FEWS Configuration Agent.

This module defines the models used by the agent to query and analyze FEWS configurations.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
import sqlite3

# Define ToolCallTracker directly here to avoid circular imports
class ToolCallTracker:
    """Track tool calls made by the agent."""
    
    def __init__(self):
        """Initialize a new tracker."""
        self.calls = []
        self.reasoning = None
    
    def clear(self):
        """Clear all tracked calls."""
        self.calls = []
        self.reasoning = None
    
    def set_reasoning(self, reasoning):
        """Set the reasoning for the next tool call."""
        self.reasoning = reasoning
    
    def log_call(self, tool_name, input_data, output_data=None, error=None):
        """Log a tool call with its input, output, and any errors."""
        self.calls.append({
            "tool": tool_name,
            "input": input_data,
            "output": output_data,
            "error": error,
            "success": error is None,
            "reasoning": self.reasoning
        })
        # Reset reasoning after logging
        self.reasoning = None
    
    def get_summary(self):
        """Get a summary of tool calls."""
        if not self.calls:
            return {}
            
        tools_used = {}
        for call in self.calls:
            tool = call["tool"]
            if tool in tools_used:
                tools_used[tool] += 1
            else:
                tools_used[tool] = 1
                
        return {
            "total_calls": len(self.calls),
            "tools_used": tools_used,
            "success_rate": sum(1 for c in self.calls if c["success"]) / len(self.calls)
        }


class Deps(BaseModel):
    """Dependencies for the FEWS Configuration Agent."""
    db_path: str
    db_connection: Any
    tracker: Any
    db_schema: Optional[Dict[str, Any]] = None


class SQLQueryInput(BaseModel):
    """Input for SQL query execution."""
    query: str = Field(..., description="SQL query to execute")


class SQLQueryOutput(BaseModel):
    """
    Output from SQL query.
    
    Attributes:
        results: Query results as list of dictionaries
        column_names: Names of columns in the result set, preserving original order
        row_count: Number of rows returned by the query
        query_executed: The SQL query that was executed
    """
    results: List[Dict[str, Any]] = Field(..., description="Results of the SQL query")
    column_names: List[str] = Field(..., description="Column names of the result set in original order")
    row_count: int = Field(..., description="Number of rows returned by the query")
    query_executed: str = Field(..., description="The SQL query that was executed")


class WorkflowSearchInput(BaseModel):
    """
    Input for workflow search.
    
    Attributes:
        name_pattern: Pattern to search for in workflow name or description
    """
    name_pattern: str = Field(..., description="Pattern to search for in workflow name or description")


class TimeSeriesSearchInput(BaseModel):
    """
    Input for time series search.
    
    Attributes:
        parameter_id: Pattern to search for in parameter ID
        qualifier_pattern: Pattern to search for in qualifier
        module_instance: Pattern to search for in module instance
    """
    parameter_id: Optional[str] = Field(None, description="Pattern to search for in parameter ID")
    qualifier_pattern: Optional[str] = Field(None, description="Pattern to search for in qualifier")
    module_instance: Optional[str] = Field(None, description="Pattern to search for in module instance")


class TransformationSearchInput(BaseModel):
    """
    Input for transformation search.
    
    Attributes:
        description_pattern: Pattern to search for in transformation description
    """
    description_pattern: str = Field(..., description="Pattern to search for in transformation description")


class DependencyAnalysisInput(BaseModel):
    """
    Input for dependency analysis.
    
    Attributes:
        entity_type: Type of entity to analyze (timeseries, transformation, workflow)
        entity_id: ID of the entity to analyze
    """
    entity_type: str = Field(..., description="Type of entity to analyze (timeseries, transformation, workflow)")
    entity_id: int = Field(..., description="ID of the entity to analyze")


class EntityType(str, Enum):
    """Valid entity types for visualization."""
    TIMESERIES = "timeseries"
    TRANSFORMATION = "transformation"
    WORKFLOW = "workflow"


class VisualizationRequestInput(BaseModel):
    """Input for visualization requests."""
    entity_type: EntityType = Field(..., description="Type of entity to visualize")
    entity_id: int = Field(..., description="ID of the entity to visualize")
    depth: Optional[int] = Field(default=5, description="Maximum depth for recursive queries")


class EndpointPathRequest(BaseModel):
    """
    Input specifically for endpoint to root path requests.
    This model enforces that we only work with timeseries entities.
    """
    entity_id: int = Field(..., description="ID of the timeseries set to trace")
    depth: Optional[int] = Field(default=5, description="Maximum depth for recursive queries")
    
    @property
    def entity_type(self) -> Literal["timeseries"]:
        """Always returns 'timeseries' as this is specific to timeseries endpoints."""
        return "timeseries"


class PathData(BaseModel):
    """Data structure for a path from endpoint to root."""
    type: str = Field("path_data", description="Type of data")
    data: List[Dict[str, Any]] = Field(..., description="List of path components")


class PathFlowOutput(BaseModel):
    """Output for path flow visualization."""
    type: str = Field("streamlit_flow", description="Type of visualization")
    state: Any = Field(..., description="Streamlit flow state")


class PathTableOutput(BaseModel):
    """Output for path table visualization."""
    type: str = Field("table", description="Type of visualization")
    data: Any = Field(..., description="Table data")


class RenderPathInput(BaseModel):
    """Input for rendering a path as a flow diagram."""
    path_data: PathData = Field(..., description="Path data to render as a flow diagram")


class RenderPathTableInput(BaseModel):
    """Input for rendering a path as a table."""
    path_data: PathData = Field(..., description="Path data to render as a table")


class FlowState(BaseModel):
    """State for streamlit-flow visualization."""
    type: str = Field("streamlit_flow", description="Type of visualization")
    state: Dict[str, Any] = Field(..., description="Streamlit flow state containing nodes and edges") 