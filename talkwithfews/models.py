"""
Pydantic models for the FEWS Configuration Agent.

This module defines the models used by the agent to query and analyze FEWS configurations.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import sqlite3


class ToolCallTracker:
    """Class to track tool calls and their results.
    
    This class is used to maintain a history of tool calls and their outcomes,
    which can be useful for debugging and analysis.
    """
    def __init__(self):
        self.calls = []


class Transformation(BaseModel):
    """Model representing a transformation in the FEWS configuration.
    
    A transformation is a process that converts input time series into output time series
    according to specific rules defined in a module configuration.
    """
    trafo_id: int = Field(..., description="Unique identifier of the transformation")
    trafo_desc: str = Field(..., description="Description of what the transformation does")
    ord_nr: int = Field(..., description="Order number indicating the sequence in the module configuration")
    module_config_id: int = Field(..., description="Unique identifier of the module configuration")
    module_config: str = Field(..., description="Name of the module instance containing this transformation")
    workflow_id: int = Field(..., description="Unique identifier of the workflow")
    workflow_name: str = Field(..., description="Name of the workflow")
    workflow_desc: str = Field(..., description="Description of the workflow")
    inout: str = Field(..., description="Indicates if the time series is used as input ('in') or output ('out')")
    linked_tss_modins: Optional[str] = Field(None, description="Module instance of the linked time series")
    linked_tss_parid: Optional[str] = Field(None, description="Parameter ID of the linked time series")
    linked_tss_qualifiers: Optional[str] = Field(None, description="Qualifiers of the linked time series")


class TransformationSearchResult(BaseModel):
    """Model representing a transformation search result.
    
    A transformation search result includes the transformation details and its context
    within a workflow and module configuration.
    """
    id: int = Field(..., description="Unique identifier of the transformation")
    desc: str = Field(..., description="Description of what the transformation does")
    ord_nr: int = Field(..., description="Order number indicating the sequence in the module configuration")
    mic_id: int = Field(..., description="Unique identifier of the module configuration")
    modins: str = Field(..., description="Name of the module instance containing this transformation")
    workflow_id: int = Field(..., description="Unique identifier of the workflow")
    workflow_name: str = Field(..., description="Name of the workflow")
    workflow_desc: str = Field(..., description="Description of the workflow")


class TransformationSearchInput(BaseModel):
    """Model for the input of the search_transformations tool.
    
    This model defines the parameters to search for transformations.
    
    Attributes:
        description_pattern: Pattern to search for in transformation description
        workflow_name: Optional pattern to filter by workflow name
        module_config: Optional pattern to filter by module configuration name
        max_depth: Optional maximum depth for hierarchical results
    """
    description_pattern: str = Field(..., description="Pattern to search for in transformation description")
    workflow_name: Optional[str] = Field(None, description="Optional pattern to filter by workflow name")
    module_config: Optional[str] = Field(None, description="Optional pattern to filter by module configuration name")
    max_depth: Optional[int] = Field(None, description="Optional maximum depth for hierarchical results")


class TransformationSearchOutput(BaseModel):
    """Model for the output of the search_transformations tool.
    
    This model provides the search results including both structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[TransformationSearchResult] = Field(..., description="List of matching transformations with their context")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the search results in a human-readable format")


class TimeSeriesSearchInput(BaseModel):
    """Model for the input of the search_timeseries tool.
    
    This model defines the parameters to search for time series.
    
    Attributes:
        parameter_id: Optional pattern to search for in parameter ID
        qualifier_pattern: Optional pattern to search for in qualifier
        module_instance: Optional pattern to search for in module instance
        endpoint: Optional filter for endpoint status
        include_transformations: Whether to include transformation information
    """
    parameter_id: Optional[str] = Field(None, description="Pattern to search for in parameter ID")
    qualifier_pattern: Optional[str] = Field(None, description="Pattern to search for in qualifier")
    module_instance: Optional[str] = Field(None, description="Pattern to search for in module instance")
    endpoint: Optional[bool] = Field(None, description="Filter by endpoint status (True for endpoints, False for non-endpoints)")
    include_transformations: bool = Field(False, description="Whether to include transformation information")


class TimeSeriesProperties(BaseModel):
    """Model representing the core properties of a time series in the FEWS configuration.
    
    A time series is a sequence of data points indexed in time order. In FEWS, each time series
    has specific properties that define its characteristics and how it's used in the system.
    """
    id: int = Field(..., description="Unique identifier of the time series")
    modins: str = Field(..., description="Module instance that owns or manages this time series")
    vtype: str = Field(..., description="Value type of the time series (e.g., 'scalar', 'vector')")
    parid: str = Field(..., description="Parameter identifier (e.g., 'bodemvocht_e' for soil moisture)")
    qualifiers: str = Field(..., description="Additional qualifiers that specify the time series (e.g., '30cm_minmv' for 30cm minimum value)")
    tstype: str = Field(..., description="Type of time series (e.g., 'external historical', 'internal')")
    timess: str = Field(..., description="Time step of the time series (e.g., '10minute', '1hour')")
    description: str = Field(..., description="Formatted string describing the time series using the standard template")
    endpoint: bool = Field(False, description="Whether this time series is an endpoint")
    endpoint_desc: Optional[str] = Field(None, description="Endpoint description if the time series is an endpoint")
    transformations: Optional[List[Transformation]] = Field(None, description="Optional list of transformations that use this time series as input or output")


class TimeSeriesSearchResult(TimeSeriesProperties):
    """Model representing a time series search result.
    
    A time series search result extends the base time series properties with optional
    transformation information for search results.
    """
    transformations: Optional[List[Transformation]] = Field(None, description="Optional list of associated transformations")


class TimeSeriesSearchOutput(BaseModel):
    """Model for the output of the search_timeseries tool.
    
    This model provides the search results including both structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[TimeSeriesSearchResult] = Field(..., description="List of matching time series")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the search results in a human-readable format")


class Deps:
    """
    Dependencies for the FEWS Configuration Agent.
    
    Attributes:
        db_connection: SQLite database connection
        db_path: Path to the SQLite database
        schema: Comprehensive database schema information
        tracker: Tool call tracker
    """
    def __init__(self, db_path: str = None, db_connection: sqlite3.Connection = None, tracker: ToolCallTracker = None):
        self.db_path = db_path
        self.db_connection = db_connection
        self.schema: Optional[Dict[str, Any]] = None
        self.tracker = tracker


class SQLQueryInput(BaseModel):
    """
    Input for SQL query.
    
    Attributes:
        query: SQL query to execute
    """
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


class DescribeTimeSeriesOutput(BaseModel):
    """Model for the output of the describe_timeseries tool.
    
    This model provides a complete description of a time series, including both its structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[TimeSeriesProperties] = Field(..., description="List containing the time series properties and its associated transformations")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the time series information in a human-readable format, including properties and transformations tables")


class DescribeTimeSeriesInput(BaseModel):
    """Model for the input of the describe_timeseries tool.
    
    This model defines the required parameters to describe a specific time series.
    
    Attributes:
        timeseries_id: The unique identifier of the time series to describe
        include_transformations: Whether to include information about transformations using this time series
    """
    timeseries_id: int = Field(..., description="The unique identifier of the time series to describe")
    include_transformations: bool = Field(True, description="Whether to include information about transformations using this time series")


class WorkflowDetailsInput(BaseModel):
    """Model for the input of the get_workflow_details tool.
    
    This model defines the required parameters to get details about a specific workflow.
    
    Attributes:
        workflow_id: The unique identifier of the workflow to describe
    """
    workflow_id: int = Field(..., description="The unique identifier of the workflow to describe")


class ModuleInstanceCall(BaseModel):
    """Model representing a module instance call within a workflow.
    
    A module instance call represents the execution of a specific module configuration
    within a workflow, including its order and description.
    """
    mic_id: int = Field(..., description="Unique identifier of the module instance call")
    modins: str = Field(..., description="Name of the module instance being called")
    ord_nr: int = Field(..., description="Order number indicating the sequence in the workflow")


class WorkflowDetails(BaseModel):
    """Model representing the details of a workflow.
    
    A workflow is a sequence of module instance calls that define a process in FEWS.
    """
    id: int = Field(..., description="Unique identifier of the workflow")
    wf_id: str = Field(..., description="Name of the workflow")
    desc: str = Field(..., description="Description of the workflow's purpose")
    wffn: str = Field(..., description="Workflow function name")
    module_calls: List[ModuleInstanceCall] = Field(..., description="List of module instance calls in this workflow")


class WorkflowDetailsOutput(BaseModel):
    """Model for the output of the get_workflow_details tool.
    
    This model provides a complete description of a workflow, including both its structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[WorkflowDetails] = Field(..., description="List containing the workflow details and its associated module calls")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the workflow information in a human-readable format")


class TransformationDetailsInput(BaseModel):
    """Model for the input of the get_transformation_details tool.
    
    This model defines the required parameters to get details about a specific transformation.
    
    Attributes:
        transformation_id: The unique identifier of the transformation to describe
    """
    transformation_id: int = Field(..., description="The unique identifier of the transformation to describe")


class TimeSeriesLink(BaseModel):
    """Model representing a time series linked to a transformation.
    
    A time series link represents how a time series is connected to a transformation,
    either as input or output. The time series properties can be retrieved using the tss_id.
    """
    inout: str = Field(..., description="Indicates if the time series is used as input ('in') or output ('out')")
    tss_id: int = Field(..., description="Unique identifier of the time series")


class TransformationDetails(BaseModel):
    """Model representing the details of a transformation.
    
    A transformation is a process that converts input time series into output time series
    according to specific rules defined in a module configuration.
    """
    id: int = Field(..., description="Unique identifier of the transformation")
    desc: str = Field(..., description="Description of what the transformation does")
    ord_nr: int = Field(..., description="Order number indicating the sequence in the module configuration")
    config_file: str = Field(..., description="Relative path to the module configuration file")
    mic_id: int = Field(..., description="Unique identifier of the module configuration")
    modins: str = Field(..., description="Name of the module instance containing this transformation")
    time_series_links: List[TimeSeriesLink] = Field(..., description="List of time series connected to this transformation")


class TransformationDetailsOutput(BaseModel):
    """Model for the output of the get_transformation_details tool.
    
    This model provides a complete description of a transformation, including both its structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[TransformationDetails] = Field(..., description="List containing the transformation details and its associated time series links")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the transformation information in a human-readable format")


class DependencyAnalysisOutput(BaseModel):
    """Model for the output of the analyze_dependencies tool.
    
    This model provides a complete description of dependencies, including both structured data
    and a formatted markdown representation for display purposes.
    """
    results: List[Dict[str, Any]] = Field(..., description="List containing the dependency analysis results")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the dependency information in a human-readable format")


class DependencyAnalysisInput(BaseModel):
    """Model for the input of the analyze_dependencies tool.
    
    This model defines the required parameters to analyze dependencies.
    
    Attributes:
        entity_type: Type of entity to analyze (timeseries, transformation, workflow)
        entity_id: ID of the entity to analyze
        direction: Direction of dependencies to analyze (upstream, downstream, or both)
    """
    entity_type: str = Field(..., description="Type of entity to analyze (timeseries, transformation, workflow)")
    entity_id: int = Field(..., description="ID of the entity to analyze")
    direction: str = Field("both", description="Direction of dependencies to analyze (upstream, downstream, or both)")


class GraphNode(BaseModel):
    """Model representing a node in a graph visualization.
    
    A node represents an entity (time series, transformation, or workflow) in the graph.
    
    Attributes:
        id: Unique identifier of the entity
        type: Type of entity (timeseries, transformation, workflow)
        label: Display label for the node
        properties: Additional properties to display
        level: Optional level in the hierarchy (for hierarchical layouts)
    """
    id: int = Field(..., description="Unique identifier of the entity")
    type: str = Field(..., description="Type of entity (timeseries, transformation, workflow)")
    label: str = Field(..., description="Display label for the node")
    properties: Dict[str, str] = Field(default_factory=dict, description="Additional properties to display")
    level: Optional[int] = Field(None, description="Optional level in the hierarchy")


class GraphEdge(BaseModel):
    """Model representing an edge in a graph visualization.
    
    An edge represents a relationship between entities in the graph.
    
    Attributes:
        source_id: ID of the source node
        target_id: ID of the target node
        type: Type of relationship (e.g., 'input', 'output', 'calls')
        label: Optional label to display on the edge
        properties: Additional properties of the relationship
    """
    source_id: int = Field(..., description="ID of the source node")
    target_id: int = Field(..., description="ID of the target node")
    type: str = Field(..., description="Type of relationship")
    label: Optional[str] = Field(None, description="Optional label to display on the edge")
    properties: Dict[str, str] = Field(default_factory=dict, description="Additional properties of the relationship")


class GraphLayout(BaseModel):
    """Model defining how the graph should be laid out.
    
    This model specifies the visualization parameters for the graph.
    
    Attributes:
        layout_type: Type of layout to use (e.g., 'hierarchical', 'force-directed')
        direction: Direction for hierarchical layouts (e.g., 'LR', 'TB')
        max_depth: Maximum depth for hierarchical layouts
        node_spacing: Spacing between nodes
        level_spacing: Spacing between levels in hierarchical layouts
    """
    layout_type: str = Field("hierarchical", description="Type of layout to use")
    direction: str = Field("LR", description="Direction for hierarchical layouts")
    max_depth: Optional[int] = Field(None, description="Maximum depth for hierarchical layouts")
    node_spacing: int = Field(50, description="Spacing between nodes")
    level_spacing: int = Field(100, description="Spacing between levels")


class GraphVisualizationInput(BaseModel):
    """Model for the input of graph visualization tools.
    
    This model defines the parameters for creating a graph visualization.
    
    Attributes:
        root_entity_type: Type of the root entity to visualize
        root_entity_id: ID of the root entity
        layout: Optional layout parameters
        include_properties: Whether to include detailed properties in the visualization
        max_nodes: Maximum number of nodes to include (for performance)
    """
    root_entity_type: str = Field(..., description="Type of the root entity to visualize")
    root_entity_id: int = Field(..., description="ID of the root entity")
    layout: Optional[GraphLayout] = Field(None, description="Optional layout parameters")
    include_properties: bool = Field(False, description="Whether to include detailed properties")
    max_nodes: Optional[int] = Field(None, description="Maximum number of nodes to include")


class GraphVisualizationOutput(BaseModel):
    """Model for the output of graph visualization tools.
    
    This model provides the graph data needed for visualization.
    
    Attributes:
        nodes: List of nodes in the graph
        edges: List of edges in the graph
        layout: Layout parameters used
        markdown_content: Optional markdown representation of the graph
    """
    nodes: List[GraphNode] = Field(..., description="List of nodes in the graph")
    edges: List[GraphEdge] = Field(..., description="List of edges in the graph")
    layout: GraphLayout = Field(..., description="Layout parameters used")
    markdown_content: Optional[str] = Field(None, description="Optional markdown representation of the graph")


class WorkflowSearchResult(BaseModel):
    """Model representing a workflow search result."""
    id: int = Field(..., description="Unique identifier of the workflow")
    wf_id: str = Field(..., description="Name of the workflow")
    desc: str = Field(..., description="Description of the workflow")
    module_config_ids: List[str] = Field(..., description="List of module configuration IDs in this workflow")


class WorkflowSearchOutput(BaseModel):
    """Model for the output of the search_workflows tool."""
    results: List[WorkflowSearchResult] = Field(..., description="List of matching workflows")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the search results in a human-readable format")


class DeadPoint(BaseModel):
    """Model representing a dead point (unused time series) in the FEWS configuration."""
    id: int = Field(..., description="Unique identifier of the time series")
    modins: str = Field(..., description="Module instance that owns this time series")
    vtype: str = Field(..., description="Value type of the time series")
    parid: str = Field(..., description="Parameter identifier")
    qualifiers: str = Field(..., description="Additional qualifiers")
    tstype: str = Field(..., description="Type of time series")
    timess: str = Field(..., description="Time step")


class DeadPointProducer(BaseModel):
    """Model representing a transformation that produces a dead point."""
    tss_id: int = Field(..., description="ID of the time series")
    trafo_id: int = Field(..., description="ID of the transformation")
    trafo_desc: str = Field(..., description="Description of the transformation")
    module_instance: str = Field(..., description="Module instance containing the transformation")
    workflow_id: str = Field(..., description="ID of the workflow")


class ModuleSummary(BaseModel):
    """Model representing a summary of dead points by module."""
    module: str = Field(..., description="Module instance name")
    count: int = Field(..., description="Number of dead points in this module")


class DeadPointsAnalysisOutput(BaseModel):
    """Model for the output of the analyze_dead_points tool."""
    count: int = Field(..., description="Total number of dead points found")
    dead_points: List[DeadPoint] = Field(..., description="List of dead points")
    module_summary: List[ModuleSummary] = Field(..., description="Summary of dead points by module")
    unique_modules: int = Field(..., description="Number of unique modules with dead points")
    parameters_affected: int = Field(..., description="Number of unique parameters affected")
    producers: Optional[Dict[int, List[DeadPointProducer]]] = Field(None, description="Transformations producing dead points, grouped by time series ID")
    recommendations: List[str] = Field(..., description="List of recommendations for addressing dead points")
    markdown_content: str = Field(..., description="Pre-formatted markdown string that displays the analysis results")


class AgentResponse(BaseModel):
    """
    Model for standardized agent responses.
    
    This model provides a consistent structure for all agent responses,
    allowing for text, tables, and diagram content.
    
    Attributes:
        markdown_text: Primary text response in markdown format
        markdown_table: Optional tabular data in markdown format
        mermaid_diagram: Optional mermaid diagram code
    """
    markdown_text: str = Field(..., description="Primary text response in markdown format")
    markdown_table: Optional[str] = Field(None, description="Optional tabular data in markdown format")
    mermaid_diagram: Optional[str] = Field(None, description="Optional mermaid diagram code, makee sure it uses nodes on a new line") 