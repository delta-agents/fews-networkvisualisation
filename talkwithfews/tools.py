"""
Tools for the FEWS Configuration Agent.

This module defines the tools used by the agent to query and analyze FEWS configurations.
"""

import sqlite3
from typing import Dict, Any
from pydantic_ai import RunContext, ModelRetry

from .models import (
    Deps,
    SQLQueryInput,
    SQLQueryOutput,
    WorkflowSearchInput,
    TimeSeriesSearchInput,
    TransformationSearchInput,
    DependencyAnalysisInput
)

from .logging_utils import log_tool_call, logger
from .schema_utils import (
    extract_llm_friendly_schema, 
    create_schema_info_dict, 
    get_table_relationships,
    diagnose_sql_error
)


@log_tool_call
async def execute_query(ctx: RunContext[Deps], input: SQLQueryInput) -> SQLQueryOutput:
    """
    Execute a SQL query on the FEWS configuration database.
    
    Args:
        ctx: RunContext with database connection
        input: SQLQueryInput containing the query to execute
        
    Returns:
        SQLQueryOutput: Results of the query with column names
    """
    try:
        # Execute the query
        cursor = ctx.deps.db_connection.cursor()
        cursor.execute(input.query)
        
        # Extract results and column names
        column_names = [description[0] for description in cursor.description] if cursor.description else []
        results = [dict(zip(column_names, row)) for row in cursor.fetchall()]
        
        # Return the query results
        return SQLQueryOutput(
            results=results, 
            column_names=column_names,
            row_count=len(results),
            query_executed=input.query
        )
    except sqlite3.Error as e:
        error_msg = f"Database error: {str(e)}"
        logger.error(f"SQL Error: {error_msg} - Query: {input.query}")
        
        # Attempt to diagnose common errors using schema_utils.diagnose_sql_error
        if hasattr(ctx.deps, 'db_schema') and ctx.deps.db_schema:
            schema_info = create_schema_info_dict(ctx.deps.db_schema)
            error_diagnosis = diagnose_sql_error(str(e), input.query, schema_info)
            if error_diagnosis:
                error_msg += f" - {error_diagnosis}"
            
        raise ModelRetry(error_msg)


@log_tool_call
async def explain_query(ctx: RunContext[Deps], input: SQLQueryInput) -> str:
    """
    Generate an explanation of what a SQL query does.
    
    Args:
        ctx: RunContext with database connection
        input: SQLQueryInput containing the query to explain
        
    Returns:
        str: Explanation of the query
    """
    # This could be enhanced with a more sophisticated query analyzer
    return f"This query: {input.query}\n\nIs designed to retrieve data from the FEWS configuration database."


@log_tool_call
async def search_workflows(ctx: RunContext[Deps], input: WorkflowSearchInput) -> SQLQueryOutput:
    """
    Search for workflows by name pattern.
    
    Args:
        ctx: RunContext with database connection
        input: WorkflowSearchInput containing the name pattern
        
    Returns:
        SQLQueryOutput: Matching workflows
    """
    query = f"""
    SELECT id, wf_id, desc, wffn
    FROM call_stacks
    WHERE wf_id LIKE '%{input.name_pattern}%' OR desc LIKE '%{input.name_pattern}%'
    ORDER BY wf_id
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def get_workflow_details(ctx: RunContext[Deps], input: dict) -> SQLQueryOutput:
    """
    Get detailed information about a specific workflow.
    
    Args:
        ctx: RunContext with database connection
        input: Dictionary with workflow_id
        
    Returns:
        SQLQueryOutput: Workflow details including module instance calls
    """
    workflow_id = input.get("workflow_id")
    if not workflow_id:
        logger.warning("get_workflow_details called without workflow_id")
        raise ModelRetry("workflow_id is required")
    
    query = f"""
    SELECT cs.id, cs.wf_id, cs.desc, cs.wffn, mc.id as mic_id, mc.modins
    FROM call_stacks cs
    LEFT JOIN modins_calls mc ON cs.id = mc.call_stack_id
    WHERE cs.id = {workflow_id}
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def search_timeseries(ctx: RunContext[Deps], input: TimeSeriesSearchInput) -> SQLQueryOutput:
    """
    Search for time series sets by parameter, qualifier, or module.
    
    Args:
        ctx: RunContext with database connection
        input: TimeSeriesSearchInput containing search criteria
        
    Returns:
        SQLQueryOutput: Matching time series sets
    """
    conditions = []
    
    if input.parameter_id:
        conditions.append(f"parid LIKE '%{input.parameter_id}%'")
    
    if input.qualifier_pattern:
        conditions.append(f"qualifiers LIKE '%{input.qualifier_pattern}%'")
    
    if input.module_instance:
        conditions.append(f"modins LIKE '%{input.module_instance}%'")
    
    if not conditions:
        logger.warning("search_timeseries called without any search criteria")
        raise ModelRetry("At least one search criterion is required")
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
    SELECT id, modins, vtype, parid, qualifiers, tstype, timess
    FROM ts_sets
    WHERE {where_clause}
    ORDER BY id
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def get_timeseries_details(ctx: RunContext[Deps], input: dict) -> SQLQueryOutput:
    """
    Get detailed information about a specific time series set.
    
    Args:
        ctx: RunContext with database connection
        input: Dictionary with timeseries_id
        
    Returns:
        SQLQueryOutput: Time series details including related transformations
    """
    timeseries_id = input.get("timeseries_id")
    if not timeseries_id:
        logger.warning("get_timeseries_details called without timeseries_id")
        raise ModelRetry("timeseries_id is required")
    
    query = f"""
    SELECT ts.id, ts.modins, ts.vtype, ts.parid, ts.qualifiers, ts.tstype, ts.timess,
           l.inout, t.id as trafo_id, t.desc as trafo_desc, t.ord_nr
    FROM ts_sets ts
    LEFT JOIN links l ON ts.id = l.tss_id
    LEFT JOIN trafos t ON l.trafo_id = t.id
    WHERE ts.id = {timeseries_id}
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def search_transformations(ctx: RunContext[Deps], input: TransformationSearchInput) -> SQLQueryOutput:
    """
    Search for transformations by description pattern.
    
    Args:
        ctx: RunContext with database connection
        input: TransformationSearchInput containing the description pattern
        
    Returns:
        SQLQueryOutput: Matching transformations
    """
    query = f"""
    SELECT t.id, t.desc, t.ord_nr, t.mic_id, mc.modins
    FROM trafos t
    JOIN modins_calls mc ON t.mic_id = mc.id
    WHERE t.desc LIKE '%{input.description_pattern}%'
    ORDER BY t.id
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def get_transformation_details(ctx: RunContext[Deps], input: dict) -> SQLQueryOutput:
    """
    Get detailed information about a specific transformation.
    
    Args:
        ctx: RunContext with database connection
        input: Dictionary with transformation_id
        
    Returns:
        SQLQueryOutput: Transformation details including inputs and outputs
    """
    transformation_id = input.get("transformation_id")
    if not transformation_id:
        logger.warning("get_transformation_details called without transformation_id")
        raise ModelRetry("transformation_id is required")
    
    query = f"""
    SELECT t.id, t.desc, t.ord_nr, t.mic_id, mc.modins,
           l.inout, ts.id as tss_id, ts.parid, ts.qualifiers
    FROM trafos t
    JOIN modins_calls mc ON t.mic_id = mc.id
    LEFT JOIN links l ON t.id = l.trafo_id
    LEFT JOIN ts_sets ts ON l.tss_id = ts.id
    WHERE t.id = {transformation_id}
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def analyze_upstream_dependencies(ctx: RunContext[Deps], input: DependencyAnalysisInput) -> SQLQueryOutput:
    """
    Find what produces a specific entity.
    
    Args:
        ctx: RunContext with database connection
        input: DependencyAnalysisInput containing entity details
        
    Returns:
        SQLQueryOutput: Upstream dependencies
    """
    if input.entity_type == "timeseries":
        # Find transformations that produce this time series
        query = f"""
        SELECT t.id, t.desc, t.mic_id, mc.modins
        FROM trafos t
        JOIN links l ON t.id = l.trafo_id
        JOIN modins_calls mc ON t.mic_id = mc.id
        WHERE l.tss_id = {input.entity_id} AND l.inout = 'out'
        """
    elif input.entity_type == "transformation":
        # Find inputs to this transformation
        query = f"""
        SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype
        FROM ts_sets ts
        JOIN links l ON ts.id = l.tss_id
        WHERE l.trafo_id = {input.entity_id} AND l.inout = 'in'
        """
    elif input.entity_type == "workflow":
        # Find workflows that call this workflow
        query = f"""
        SELECT parent.id, parent.wf_id, parent.desc
        FROM call_stacks parent
        JOIN call_stacks child ON child.parent_id = parent.id
        WHERE child.id = {input.entity_id}
        """
    else:
        logger.warning(f"analyze_upstream_dependencies called with unknown entity type: {input.entity_type}")
        raise ModelRetry(f"Unknown entity type: {input.entity_type}")
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def analyze_downstream_dependencies(ctx: RunContext[Deps], input: DependencyAnalysisInput) -> SQLQueryOutput:
    """
    Find what consumes a specific entity.
    
    Args:
        ctx: RunContext with database connection
        input: DependencyAnalysisInput containing entity details
        
    Returns:
        SQLQueryOutput: Downstream dependencies
    """
    if input.entity_type == "timeseries":
        # Find transformations that consume this time series
        query = f"""
        SELECT t.id, t.desc, t.mic_id, mc.modins
        FROM trafos t
        JOIN links l ON t.id = l.trafo_id
        JOIN modins_calls mc ON t.mic_id = mc.id
        WHERE l.tss_id = {input.entity_id} AND l.inout = 'in'
        """
    elif input.entity_type == "transformation":
        # Find outputs from this transformation
        query = f"""
        SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype
        FROM ts_sets ts
        JOIN links l ON ts.id = l.tss_id
        WHERE l.trafo_id = {input.entity_id} AND l.inout = 'out'
        """
    elif input.entity_type == "workflow":
        # Find workflows called by this workflow
        query = f"""
        SELECT child.id, child.wf_id, child.desc
        FROM call_stacks child
        WHERE child.parent_id = {input.entity_id}
        """
    else:
        logger.warning(f"analyze_downstream_dependencies called with unknown entity type: {input.entity_type}")
        raise ModelRetry(f"Unknown entity type: {input.entity_type}")
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def find_workflow_call_hierarchy(ctx: RunContext[Deps], input: dict) -> SQLQueryOutput:
    """
    Trace workflow call stacks.
    
    Args:
        ctx: RunContext with database connection
        input: Dictionary with root_workflow_id
        
    Returns:
        SQLQueryOutput: Workflow call hierarchy
    """
    root_workflow_id = input.get("root_workflow_id")
    if not root_workflow_id:
        logger.warning("find_workflow_call_hierarchy called without root_workflow_id")
        raise ModelRetry("root_workflow_id is required")
    
    query = f"""
    WITH RECURSIVE workflow_hierarchy AS (
        SELECT id, wf_id, desc, parent_id, 0 AS level
        FROM call_stacks
        WHERE id = {root_workflow_id}
        
        UNION ALL
        
        SELECT cs.id, cs.wf_id, cs.desc, cs.parent_id, wh.level + 1
        FROM call_stacks cs
        JOIN workflow_hierarchy wh ON cs.parent_id = wh.id
    )
    SELECT id, wf_id, desc, parent_id, level
    FROM workflow_hierarchy
    ORDER BY level, wf_id
    """
    
    return await execute_query(ctx, SQLQueryInput(query=query))


@log_tool_call
async def get_database_schema(ctx: RunContext[Deps], input: dict = None) -> Dict[str, Any]:
    """
    Get the database schema information to understand the structure of the FEWS configuration database.
    
    Args:
        ctx: RunContext with database connection
        input: Optional dict with parameters (not used currently)
        
    Returns:
        Dict[str, Any]: Database schema information
    """
    try:
        # If we already have schema info, use it
        if hasattr(ctx.deps, 'db_schema') and ctx.deps.db_schema:
            logger.info("Using cached schema information")
            schema = ctx.deps.db_schema
            
            # Return simplified view of schema for tool response
            return {
                "tables": create_schema_info_dict(schema),
                "relationships": get_table_relationships(schema),
                "sample_data": schema.get("sample_data", {})
            }
        
        # Otherwise, extract the schema
        db_path = ctx.deps.db_path
        if not db_path:
            raise ModelRetry("No database path provided. Cannot extract schema information.")
            
        # Extract schema using schema_utils
        logger.info(f"Extracting schema from database: {db_path}")
        schema = extract_llm_friendly_schema(db_path)
        
        # Cache schema for future use
        ctx.deps.db_schema = schema
        
        # Return formatted schema information
        return {
            "tables": create_schema_info_dict(schema),
            "relationships": get_table_relationships(schema),
            "sample_data": schema.get("sample_data", {})
        }
        
    except Exception as e:
        error_msg = f"Error retrieving database schema: {str(e)}"
        logger.error(error_msg)
        raise ModelRetry(error_msg)


@log_tool_call
async def analyze_dead_points(ctx: RunContext[Deps], input: dict = None) -> Dict[str, Any]:
    """
    Identify "dead points" in the FEWS configuration - time series sets that are 
    neither used as inputs for any transformation nor marked as endpoints.
    
    Args:
        ctx: RunContext with database connection
        input: Optional dict with parameters (include_producers=True/False)
        
    Returns:
        Dict[str, Any]: Analysis of dead points
    """
    try:
        # Check parameters
        include_producers = input.get("include_producers", True) if input else True
        
        # Execute query to find dead points
        dead_points_query = """
        SELECT ts.id, ts.modins, ts.parid, ts.qualifiers, ts.tstype, ts.timess
        FROM ts_sets ts
        WHERE ts.id NOT IN (
            -- TSS used as inputs for transformations
            SELECT DISTINCT tss_id 
            FROM links 
            WHERE inout = 'in'
        )
        AND ts.id NOT IN (
            -- TSS marked as endpoints
            SELECT tss_id 
            FROM endpoints
        )
        ORDER BY ts.modins, ts.parid
        """
        
        dead_points_result = await execute_query(ctx, SQLQueryInput(query=dead_points_query))
        
        # If no dead points found, return early
        if not dead_points_result.results:
            return {
                "count": 0,
                "dead_points": [],
                "summary": "No dead points found in the configuration."
            }
        
        # Get list of dead point IDs
        dead_point_ids = [row["id"] for row in dead_points_result.results]
        
        # Analyze by module instance
        module_counts = {}
        for row in dead_points_result.results:
            module = row["modins"]
            if module in module_counts:
                module_counts[module] += 1
            else:
                module_counts[module] = 1
        
        # Sort modules by count (descending)
        module_summary = [
            {"module": module, "count": count}
            for module, count in sorted(module_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Prepare result dictionary
        result = {
            "count": len(dead_points_result.results),
            "dead_points": dead_points_result.results,
            "module_summary": module_summary,
            "unique_modules": len(module_counts),
            "parameters_affected": len(set(row["parid"] for row in dead_points_result.results))
        }
        
        # Optionally find transformations that produce these dead points
        if include_producers and dead_point_ids:
            # Instead of using placeholders with parameters, use a simpler approach
            # Convert the list of IDs to a comma-separated string
            id_list = ", ".join(str(id) for id in dead_point_ids)
            
            producers_query = f"""
            SELECT l.tss_id, t.id AS trafo_id, t.desc AS trafo_desc, 
                  m.modins AS module_instance, c.wf_id AS workflow_id
            FROM links l
            JOIN trafos t ON l.trafo_id = t.id
            JOIN modins_calls m ON t.mic_id = m.id
            JOIN call_stacks c ON m.call_stack_id = c.id
            WHERE l.tss_id IN ({id_list})
            AND l.inout = 'out'
            ORDER BY l.tss_id
            """
            
            # Execute the query directly without parameters
            producers_result = await execute_query(ctx, SQLQueryInput(query=producers_query))
            
            if producers_result.results:
                # Group producers by time series ID
                producers_by_tss = {}
                for row in producers_result.results:
                    tss_id = row["tss_id"]
                    if tss_id not in producers_by_tss:
                        producers_by_tss[tss_id] = []
                    producers_by_tss[tss_id].append(row)
                
                result["producers"] = producers_by_tss
        
        # Add recommendations
        result["recommendations"] = [
            "Review the identified dead points to determine if they are needed",
            "Consider removing unused time series sets to simplify configuration",
            "Check if any dead points should be marked as endpoints",
            "Verify if transformations producing these time series are working as expected"
        ]
        
        logger.info(f"Found {result['count']} dead points across {result['unique_modules']} modules")
        return result
        
    except Exception as e:
        error_msg = f"Error analyzing dead points: {str(e)}"
        logger.error(error_msg)
        raise ModelRetry(error_msg) 