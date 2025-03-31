"""
Interface to the FEWS configuration analysis tools.

This module provides a clean interface to the underlying tools from the talkwithfews package,
allowing them to be called directly from the UI components without going through the agent.
"""
import asyncio
from typing import Dict, Any, Optional, List, Union
import sqlite3
import threading

from talkwithfews.models import (
    WorkflowSearchInput, 
    TimeSeriesSearchInput,
    TransformationSearchInput,
    WorkflowDetailsInput,
    TimeSeriesSearchOutput,
    WorkflowSearchOutput,
    TransformationSearchOutput,
    WorkflowDetailsOutput,
    DependencyAnalysisInput,
    DependencyAnalysisOutput,
    DescribeTimeSeriesInput,
    DescribeTimeSeriesOutput,
    TransformationDetailsInput,
    TransformationDetailsOutput,
    GraphVisualizationInput,
    GraphVisualizationOutput,
    DeadPointsAnalysisOutput,
    SQLQueryInput
)

from talkwithfews.tools import (
    search_workflows,
    search_timeseries,
    search_transformations,
    get_workflow_details,
    get_transformation_details,
    describe_timeseries,
    analyze_dependencies,
    analyze_dead_points,
    visualize_graph,
    execute_query
)

# Thread-local storage for database connections
local_storage = threading.local()

class ToolsInterface:
    """Interface to the FEWS analysis tools."""
    
    def __init__(self, db_path: str, log_dir: str):
        """
        Initialize the tools interface.
        
        Args:
            db_path: Path to the FEWS configuration database
            log_dir: Directory for logs
        """
        self.db_path = db_path
        self.log_dir = log_dir
        self.schema = None
        
    @property
    def db_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(local_storage, "connection") or local_storage.connection is None:
            self.connect()
        return local_storage.connection
    
    def connect(self):
        """Connect to the database in the current thread."""
        if not hasattr(local_storage, "connection") or local_storage.connection is None:
            local_storage.connection = sqlite3.connect(self.db_path)
            local_storage.connection.row_factory = sqlite3.Row
    
    def close(self):
        """Close the database connection for the current thread."""
        if hasattr(local_storage, "connection") and local_storage.connection:
            local_storage.connection.close()
            local_storage.connection = None
    
    def _get_deps(self):
        """Get dependencies for tool calls."""
        return {
            "db_connection": self.db_connection,
            "db_path": self.db_path,
            "log_dir": self.log_dir,
            "schema": self.schema
        }
    
    def _create_context(self):
        """Create a context object for tool calls."""
        from pydantic_ai import RunContext
        from talkwithfews.models import Deps
        
        # Create a proper Deps object with only the expected parameters
        deps = Deps(
            db_path=self.db_path, 
            db_connection=self.db_connection
        )
        
        # Add dummy values for required parameters
        return RunContext(
            deps=deps,
            model="mock-model",
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            prompt="mock-prompt"
        )
    
    async def search_workflows(self, name_pattern: str) -> WorkflowSearchOutput:
        """Search for workflows by name pattern."""
        self.connect()
        ctx = self._create_context()
        input_data = WorkflowSearchInput(name_pattern=name_pattern)
        return await search_workflows(ctx, input_data)
    
    async def search_timeseries(self, 
                               parameter_id: Optional[str] = None, 
                               qualifier_pattern: Optional[str] = None,
                               module_instance: Optional[str] = None,
                               endpoint: Optional[Any] = None) -> TimeSeriesSearchOutput:
        """Search for time series sets by parameter, qualifier, module, or endpoint status/description."""
        self.connect()
        
        # Construct a custom query that considers the endpoint parameter
        query = """
            SELECT ts.id, ts.modins, ts.vtype, ts.parid, ts.qualifiers, ts.tstype, ts.timess,
                   CASE WHEN e.tss_id IS NOT NULL THEN 1 ELSE 0 END as is_endpoint,
                   e.desc as endpoint_desc
            FROM ts_sets ts
        """
        
        conditions = []
        
        # Handle endpoint parameter based on its type
        if endpoint is not None:
            if isinstance(endpoint, bool):
                # Boolean case - filter by endpoint existence
                if endpoint:
                    # Show only endpoints
                    query += " INNER JOIN endpoints e ON ts.id = e.tss_id"
                else:
                    # Show only non-endpoints
                    query += " LEFT JOIN endpoints e ON ts.id = e.tss_id WHERE e.tss_id IS NULL"
            else:
                # String case - filter by endpoint description
                query += " INNER JOIN endpoints e ON ts.id = e.tss_id"
                
                # Escape single quotes in the endpoint description
                safe_endpoint = str(endpoint).replace("'", "''")
                conditions.append(f"e.desc = '{safe_endpoint}'")
        else:
            # No endpoint filter - still join to get endpoint status
            query += " LEFT JOIN endpoints e ON ts.id = e.tss_id"
            
        # Add other conditions
        if parameter_id:
            conditions.append(f"ts.parid LIKE '%{parameter_id}%'")
            
        if qualifier_pattern:
            conditions.append(f"ts.qualifiers LIKE '%{qualifier_pattern}%'")
            
        if module_instance:
            conditions.append(f"ts.modins LIKE '%{module_instance}%'")
            
        # Add WHERE clause if there are conditions
        if conditions:
            # If we already have a WHERE clause from non-endpoints filter, use AND
            if "WHERE" in query:
                query += " AND " + " AND ".join(conditions)
            else:
                query += " WHERE " + " AND ".join(conditions)
                
        query += " ORDER BY ts.id"
        
        # Execute the custom query
        ctx = self._create_context()
        result = await self.execute_custom_query(query=query)
        
        # Convert results to the expected output format
        from talkwithfews.models import TimeSeriesSearchResult, TimeSeriesSearchOutput
        time_series_results = []
        
        for row in result.results:
            # Create description using the standard template
            description = f"{row['modins']}|{row['vtype']}|{row['parid']}|{row['qualifiers']}|{row['tstype']}|{row['timess']}"
            is_endpoint = bool(row.get('is_endpoint', 0))
            endpoint_desc = row.get('endpoint_desc', None)
            
            time_series = TimeSeriesSearchResult(
                id=row['id'],
                modins=row['modins'],
                vtype=row['vtype'],
                parid=row['parid'],
                qualifiers=row['qualifiers'],
                tstype=row['tstype'],
                timess=row['timess'],
                description=description,
                endpoint=is_endpoint,
                endpoint_desc=endpoint_desc
            )
            time_series_results.append(time_series)
        
        # Generate markdown content
        markdown_content = f"""## Time Series Search Results
Found {len(time_series_results)} time series matching the criteria.

| ID | Module Instance | Parameter | Qualifiers | Type | Endpoint |
|----|----------------|-----------|------------|------|----------|
"""
        
        for ts in time_series_results:
            endpoint_info = ts.endpoint_desc if ts.endpoint and ts.endpoint_desc else ("✓" if ts.endpoint else "")
            markdown_content += f"| {ts.id} | {ts.modins} | {ts.parid} | {ts.qualifiers} | {ts.tstype} | {endpoint_info} |\n"
        
        return TimeSeriesSearchOutput(
            results=time_series_results,
            markdown_content=markdown_content
        )
    
    async def search_transformations(self, 
                                    description_pattern: str,
                                    workflow_name: Optional[str] = None,
                                    module_config: Optional[str] = None) -> TransformationSearchOutput:
        """Search for transformations by description and optional filters."""
        self.connect()
        ctx = self._create_context()
        input_data = TransformationSearchInput(
            description_pattern=description_pattern,
            workflow_name=workflow_name,
            module_config=module_config
        )
        return await search_transformations(ctx, input_data)
    
    async def get_workflow_details(self, workflow_id: int) -> WorkflowDetailsOutput:
        """Get detailed information about a specific workflow."""
        self.connect()
        ctx = self._create_context()
        input_data = WorkflowDetailsInput(workflow_id=workflow_id)
        return await get_workflow_details(ctx, input_data)
    
    async def get_transformation_details(self, transformation_id: int) -> TransformationDetailsOutput:
        """Get detailed information about a specific transformation."""
        self.connect()
        ctx = self._create_context()
        input_data = TransformationDetailsInput(transformation_id=transformation_id)
        return await get_transformation_details(ctx, input_data)
    
    async def describe_timeseries(self, 
                                 timeseries_id: int,
                                 include_transformations: bool = True) -> DescribeTimeSeriesOutput:
        """Get a complete description of a time series."""
        self.connect()
        ctx = self._create_context()
        input_data = DescribeTimeSeriesInput(
            timeseries_id=timeseries_id,
            include_transformations=include_transformations
        )
        return await describe_timeseries(ctx, input_data)
    
    async def analyze_dependencies(self,
                                  entity_id: int,
                                  entity_type: str) -> DependencyAnalysisOutput:
        """Analyze dependencies for a specific entity."""
        self.connect()
        ctx = self._create_context()
        input_data = DependencyAnalysisInput(
            entity_id=entity_id,
            entity_type=entity_type
        )
        return await analyze_dependencies(ctx, input_data)
    
    async def analyze_dead_points(self, include_producers: bool = True) -> DeadPointsAnalysisOutput:
        """Identify and analyze dead points in the configuration."""
        self.connect()
        ctx = self._create_context()
        input_data = {"include_producers": include_producers}
        return await analyze_dead_points(ctx, input_data)
    
    async def visualize_graph(self,
                             root_entity_id: int,
                             root_entity_type: str,
                             max_depth: int = 3,
                             max_nodes: int = 50,
                             include_properties: bool = True,
                             direction: str = "LR") -> GraphVisualizationOutput:
        """Generate a graph visualization of FEWS entities and their relationships."""
        self.connect()
        ctx = self._create_context()
        input_data = GraphVisualizationInput(
            root_entity_id=root_entity_id,
            root_entity_type=root_entity_type,
            max_nodes=max_nodes,
            include_properties=include_properties,
            layout={"direction": direction, "max_depth": max_depth}
        )
        return await visualize_graph(ctx, input_data)
    
    async def execute_custom_query(self, query: str) -> Dict[str, Any]:
        """Execute a custom SQL query."""
        self.connect()
        try:
            ctx = self._create_context()
            input_data = SQLQueryInput(query=query)
            return await execute_query(ctx, input_data)
        except Exception as e:
            # Fallback to direct execution if there's an error with the tools approach
            try:
                # Execute the query directly
                cursor = self.db_connection.cursor()
                cursor.execute(query)
                
                # Extract results and column names
                column_names = [description[0] for description in cursor.description] if cursor.description else []
                results = [dict(zip(column_names, row)) for row in cursor.fetchall()]
                
                # Create a simple result object
                return type('SQLQueryOutput', (), {
                    'results': results, 
                    'column_names': column_names,
                    'row_count': len(results),
                    'query_executed': query
                })()
            except sqlite3.Error as db_error:
                error_msg = f"Database error: {str(db_error)}"
                raise Exception(error_msg) 