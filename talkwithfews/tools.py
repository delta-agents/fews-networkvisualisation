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
    TransformationSearchOutput,
    TransformationSearchResult,
    DependencyAnalysisInput,
    DependencyAnalysisOutput,
    DescribeTimeSeriesInput,
    DescribeTimeSeriesOutput,
    TimeSeriesProperties,
    WorkflowDetailsInput,
    WorkflowDetailsOutput,
    WorkflowDetails,
    ModuleInstanceCall,
    TransformationDetailsInput,
    TransformationDetailsOutput,
    TransformationDetails,
    TimeSeriesLink,
    GraphVisualizationInput,
    GraphVisualizationOutput,
    GraphNode,
    GraphEdge,
    GraphLayout,
    WorkflowSearchOutput,
    WorkflowSearchResult,
    TimeSeriesSearchOutput,
    TimeSeriesSearchResult,
    DeadPoint,
    DeadPointProducer,
    ModuleSummary,
    DeadPointsAnalysisOutput
)

from .logging_utils import log_tool_call, logger
from .schema_utils import (
    extract_db_schema_as_dict, 
    create_schema_info_dict, 
    get_table_relationships,
    diagnose_sql_error,
    format_timeseries_description
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
        if hasattr(ctx.deps, 'schema') and ctx.deps.schema:
            schema_info = create_schema_info_dict(ctx.deps.schema)
            error_diagnosis = diagnose_sql_error(str(e), input.query, schema_info)
            if error_diagnosis:
                error_msg += f" - {error_diagnosis}"
            
        raise ModelRetry(error_msg)



@log_tool_call
async def search_workflows(ctx: RunContext[Deps], input: WorkflowSearchInput) -> WorkflowSearchOutput:
    """
    Search for workflows by name pattern.
    
    Args:
        ctx: RunContext with database connection
        input: WorkflowSearchInput containing the name pattern
        
    Returns:
        WorkflowSearchOutput: Matching workflows with formatted markdown content
    """
    query = f"""
    SELECT cs.id, cs.wf_id, cs.desc, 
           GROUP_CONCAT(mc.id) as module_config_ids
    FROM call_stacks cs
    LEFT JOIN modins_calls mc ON cs.id = mc.call_stack_id
    WHERE cs.wf_id LIKE '%{input.name_pattern}%' OR cs.desc LIKE '%{input.name_pattern}%'
    GROUP BY cs.id
    ORDER BY cs.wf_id
    """
    
    result = await execute_query(ctx, SQLQueryInput(query=query))
    
    # Convert results to WorkflowSearchResult objects
    workflow_results = [
        WorkflowSearchResult(
            id=row['id'],
            wf_id=row['wf_id'],
            desc=row['desc'],
            module_config_ids=row['module_config_ids'].split(',') if row['module_config_ids'] else []
        )
        for row in result.results
    ]
    
    # Generate markdown content
    markdown_content = f"""## Workflow Search Results
Found {len(workflow_results)} workflows matching the pattern '{input.name_pattern}'.

| ID | Workflow ID | Description | Module Config IDs |
|----|-------------|-------------|-------------------|
"""
    
    for workflow in workflow_results:
        module_configs = ', '.join(workflow.module_config_ids) if workflow.module_config_ids else 'None'
        markdown_content += f"| {workflow.id} | {workflow.wf_id} | {workflow.desc} | {module_configs} |\n"
    
    return WorkflowSearchOutput(
        results=workflow_results,
        markdown_content=markdown_content
    )


@log_tool_call
async def get_workflow_details(ctx: RunContext[Deps], input: WorkflowDetailsInput) -> WorkflowDetailsOutput:
    """
    Get detailed information about a specific workflow, including its module instance calls
    and their transformations in sequential order.
    
    Args:
        ctx: RunContext with database connection
        input: WorkflowDetailsInput containing the workflow ID
            
    Returns:
        WorkflowDetailsOutput: A complete description of the workflow including:
            - Structured data about the workflow and its module calls
            - Pre-formatted markdown content for display
    """
    # Get workflow details, module calls, and their transformations
    query = f"""
    SELECT cs.id, cs.wf_id, cs.desc, cs.wffn, 
           mc.id as mic_id, mc.modins,
           t.id as trafo_id, t.desc as trafo_desc, t.ord_nr
    FROM call_stacks cs
    LEFT JOIN modins_calls mc ON cs.id = mc.call_stack_id
    LEFT JOIN trafos t ON mc.id = t.mic_id
    WHERE cs.id = {input.workflow_id}
    ORDER BY mc.id, t.ord_nr
    """
    
    result = await execute_query(ctx, SQLQueryInput(query=query))
    
    if not result.results:
        raise ModelRetry(f"No workflow found with ID {input.workflow_id}")
    
    # Group module calls and transformations by workflow
    workflow_data = {}
    for row in result.results:
        workflow_id = row['id']
        if workflow_id not in workflow_data:
            workflow_data[workflow_id] = {
                'id': row['id'],
                'wf_id': row['wf_id'],
                'desc': row['desc'],
                'wffn': row['wffn'],
                'module_calls': {}
            }
        
        if row['mic_id']:  # Only add if there's a module call
            if row['mic_id'] not in workflow_data[workflow_id]['module_calls']:
                workflow_data[workflow_id]['module_calls'][row['mic_id']] = {
                    'mic_id': row['mic_id'],
                    'modins': row['modins'],
                    'transformations': []
                }
            
            if row['trafo_id']:  # Add transformation if it exists
                workflow_data[workflow_id]['module_calls'][row['mic_id']]['transformations'].append({
                    'id': row['trafo_id'],
                    'desc': row['trafo_desc'],
                    'ord_nr': row['ord_nr']
                })
    
    # Create markdown content
    markdown_content = f"""## Workflow: {workflow_data[input.workflow_id]['wf_id']}
**Description:** {workflow_data[input.workflow_id]['desc']}

### Basic Information
| Property | Value |
|----------|--------|
| ID | {workflow_data[input.workflow_id]['id']} |
| Function Name | {workflow_data[input.workflow_id]['wffn']} |

"""
    
    # Add module calls and transformations if they exist
    if workflow_data[input.workflow_id]['module_calls']:
        markdown_content += "### Module Calls and Their Transformations\n"
        for mic_id, module_call in workflow_data[input.workflow_id]['module_calls'].items():
            markdown_content += f"\n#### Module: {module_call['modins']}\n"
            if module_call['transformations']:
                markdown_content += "The following transformations are executed in this module:\n\n"
                markdown_content += "| Order | Transformation ID | Description |\n"
                markdown_content += "|-------|------------------|-------------|\n"
                for trafo in sorted(module_call['transformations'], key=lambda x: x['ord_nr']):
                    markdown_content += f"| {trafo['ord_nr']} | {trafo['id']} | {trafo['desc']} |\n"
            else:
                markdown_content += "This module has no transformations.\n"
    else:
        markdown_content += "### Module Calls\nThis workflow has no module calls."

    # Add Mermaid diagram
    markdown_content += "\n### Workflow Structure\n```mermaid\ngraph TD\n"
    
    # Add workflow node
    markdown_content += f"    WF[{workflow_data[input.workflow_id]['wf_id']}]:::workflow\n"
    
    # Add module nodes and their connections
    if workflow_data[input.workflow_id]['module_calls']:
        for mic_id, module_call in workflow_data[input.workflow_id]['module_calls'].items():
            # Add module node
            markdown_content += f"    M{mic_id}[{module_call['modins']}]:::module\n"
            # Connect workflow to module
            markdown_content += f"    WF --> M{mic_id}\n"
            
            # Add transformation nodes if they exist
            if module_call['transformations']:
                for trafo in sorted(module_call['transformations'], key=lambda x: x['ord_nr']):
                    # Add transformation node
                    markdown_content += f"    T{trafo['id']}[{trafo['desc']}]:::transformation\n"
                    # Connect module to transformation
                    markdown_content += f"    M{mic_id} --> T{trafo['id']}\n"
    
    # Add styles
    markdown_content += """
    classDef workflow fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef module fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef transformation fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
```\n"""
    
    # Convert module_calls dict to list for the output model
    module_calls_list = []
    for mic_id, module_call in workflow_data[input.workflow_id]['module_calls'].items():
        module_calls_list.append({
            'mic_id': module_call['mic_id'],
            'modins': module_call['modins'],
            'ord_nr': 0  # Default to 0 since we don't have module call order
        })
    
    # Create the output using Pydantic models
    return WorkflowDetailsOutput(
        results=[WorkflowDetails(**{**workflow_data[input.workflow_id], 'module_calls': module_calls_list})],
        markdown_content=markdown_content
    )


@log_tool_call
async def search_timeseries(ctx: RunContext[Deps], input: TimeSeriesSearchInput) -> TimeSeriesSearchOutput:
    """
    Search for time series sets by parameter, qualifier, module, or endpoint status.
    
    Args:
        ctx: RunContext with database connection
        input: TimeSeriesSearchInput containing search criteria
        
    Returns:
        TimeSeriesSearchOutput: Matching time series sets with formatted markdown content
    """
    # Check if we're filtering by endpoint status
    if input.endpoint is not None:
        # Create a more specific query that joins with the endpoints table
        query = """
            SELECT ts.id, ts.modins, ts.vtype, ts.parid, ts.qualifiers, ts.tstype, ts.timess,
                   CASE WHEN e.tss_id IS NOT NULL THEN 1 ELSE 0 END as is_endpoint
            FROM ts_sets ts
        """
        
        conditions = []
        
        # Join with endpoints table based on filter type
        if input.endpoint:
            query += " INNER JOIN endpoints e ON ts.id = e.tss_id"
        else:
            query += " LEFT JOIN endpoints e ON ts.id = e.tss_id WHERE e.tss_id IS NULL"
            
        # Add other conditions
        if input.parameter_id:
            conditions.append(f"ts.parid LIKE '%{input.parameter_id}%'")
            
        if input.qualifier_pattern:
            conditions.append(f"ts.qualifiers LIKE '%{input.qualifier_pattern}%'")
            
        if input.module_instance:
            conditions.append(f"ts.modins LIKE '%{input.module_instance}%'")
            
        # Add other conditions to the query
        if conditions:
            if not input.endpoint or input.endpoint:
                query += " WHERE " + " AND ".join(conditions)
            else:
                query += " AND " + " AND ".join(conditions)
                
        query += " ORDER BY ts.id"
    else:
        # Use the standard approach for non-endpoint filtering
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
        SELECT ts.id, ts.modins, ts.vtype, ts.parid, ts.qualifiers, ts.tstype, ts.timess,
               CASE WHEN e.tss_id IS NOT NULL THEN 1 ELSE 0 END as is_endpoint
        FROM ts_sets ts
        LEFT JOIN endpoints e ON ts.id = e.tss_id
        WHERE {where_clause}
        ORDER BY ts.id
        """
    
    result = await execute_query(ctx, SQLQueryInput(query=query))
    
    # Convert results to TimeSeriesSearchResult objects
    time_series_results = []
    for row in result.results:
        # Create description using the standard template
        description = f"{row['modins']}|{row['vtype']}|{row['parid']}|{row['qualifiers']}|{row['tstype']}|{row['timess']}"
        is_endpoint = bool(row.get('is_endpoint', False))
        
        time_series = TimeSeriesSearchResult(
            id=row['id'],
            modins=row['modins'],
            vtype=row['vtype'],
            parid=row['parid'],
            qualifiers=row['qualifiers'],
            tstype=row['tstype'],
            timess=row['timess'],
            description=description,
            endpoint=is_endpoint
        )
        time_series_results.append(time_series)
    
    # Generate markdown content
    markdown_content = f"""## Time Series Search Results
Found {len(time_series_results)} time series matching the criteria.

| ID | Module Instance | Type | Parameter | Qualifiers | Value Type | Time Step | Endpoint |
|----|----------------|------|-----------|------------|------------|-----------|----------|
"""
    
    for ts in time_series_results:
        is_endpoint = "✓" if ts.endpoint else ""
        markdown_content += f"| {ts.id} | {ts.modins} | {ts.tstype} | {ts.parid} | {ts.qualifiers} | {ts.vtype} | {ts.timess} | {is_endpoint} |\n"
    
    return TimeSeriesSearchOutput(
        results=time_series_results,
        markdown_content=markdown_content
    )


@log_tool_call
async def describe_timeseries(ctx: RunContext[Deps], input: DescribeTimeSeriesInput) -> DescribeTimeSeriesOutput:
    """
    Get a complete description of a time series, including its basic properties and optionally
    any transformations that use it as input or output.
    
    The time series is described by the template:
    "{modins}|{vtype}|{parid}|{qualifiers}|{tstype}|{timess}"
    
    Args:
        ctx: RunContext with database connection
        input: DescribeTimeSeriesInput containing the time series ID to describe and whether to include transformations
            
    Returns:
        DescribeTimeSeriesOutput: A complete description of the time series including:
            - Structured data about the time series and optionally its transformations
            - Pre-formatted markdown content for display
    """
    # First get the basic time series information
    base_query = f"""
    SELECT id, modins, vtype, parid, qualifiers, tstype, timess
    FROM ts_sets
    WHERE id = {input.timeseries_id}
    """
    
    base_result = await execute_query(ctx, SQLQueryInput(query=base_query))
    
    if not base_result.results:
        raise ModelRetry(f"No time series found with ID {input.timeseries_id}")
    
    # Create the time series properties
    time_series = base_result.results[0]
    time_series["description"] = format_timeseries_description(time_series)
    
    # Get transformations if requested
    if input.include_transformations:
        transformations_query = f"""
        SELECT l.inout, t.id as trafo_id, t.desc as trafo_desc, t.ord_nr,
               cs.id as workflow_id, cs.wf_id as workflow_name, cs.desc as workflow_desc,
               linked_ts.modins as linked_tss_modins, linked_ts.parid as linked_tss_parid, linked_ts.qualifiers as linked_tss_qualifiers,
               mc.modins as module_config,
               mc.id as module_config_id
        FROM links l
        JOIN trafos t ON l.trafo_id = t.id
        JOIN modins_calls mc ON t.mic_id = mc.id
        JOIN call_stacks cs ON mc.call_stack_id = cs.id
        JOIN links linked_l ON t.id = linked_l.trafo_id 
            AND linked_l.tss_id != {input.timeseries_id}
        JOIN ts_sets linked_ts ON linked_l.tss_id = linked_ts.id
        WHERE l.tss_id = {input.timeseries_id}
        ORDER BY cs.wf_id, t.ord_nr
        """
        
        transformations_result = await execute_query(ctx, SQLQueryInput(query=transformations_query))
        time_series["transformations"] = transformations_result.results
    
    # Create markdown content
    markdown_content = f"""## Time Series {time_series['id']}
**Description:** {time_series['description']}

### Properties
| Property | Value |
|----------|--------|
| Module Instance | {time_series['modins']} |
| Value Type | {time_series['vtype']} |
| Parameter ID | {time_series['parid']} |
| Qualifiers | {time_series['qualifiers']} |
| Time Series Type | {time_series['tstype']} |
| Time Step | {time_series['timess']} |

"""
    
    # Add transformations table if they exist and were requested
    if input.include_transformations and time_series.get('transformations'):
        markdown_content += """### Transformations
| Module Config | Transformation | Type | Workflow Name | Description |
|--------------|---------------|------|--------------|-------------|
"""
        for trans in time_series['transformations']:
            markdown_content += f"| {trans['module_config']} | {trans['trafo_desc']} | {trans['inout']} | {trans['workflow_name']} | {trans['workflow_desc']} |\n"
    elif input.include_transformations:
        markdown_content += "### Transformations\nNo transformations found"
    
    # Create the output using Pydantic models
    return DescribeTimeSeriesOutput(
        results=[TimeSeriesProperties(**time_series)],
        markdown_content=markdown_content
    )


@log_tool_call
async def search_transformations(
    ctx: RunContext[Deps],
    input_data: TransformationSearchInput
) -> TransformationSearchOutput:
    """Search for transformations matching the given criteria.
    
    This tool searches for transformations based on their description and optionally
    filters by workflow name and module configuration. It supports limiting the depth
    of hierarchical results.
    
    Args:
        ctx: RunContext with database connection
        input_data: Search criteria including description pattern and optional filters
        
    Returns:
        TransformationSearchOutput containing matching transformations
    """
    # Build the base query
    query = """
    SELECT DISTINCT
        t.id,
        t.desc,
        t.ord_nr,
        t.mic_id,
        mc.modins,
        cs.id as workflow_id,
        cs.wf_id as workflow_name,
        cs.desc as workflow_desc
    FROM trafos t
    JOIN modins_calls mc ON t.mic_id = mc.id
    JOIN call_stacks cs ON mc.call_stack_id = cs.id
    WHERE t.desc LIKE ?
    """
    params = [f"%{input_data.description_pattern}%"]
    
    # Add optional filters
    if input_data.workflow_name:
        query += " AND cs.wf_id LIKE ?"
        params.append(f"%{input_data.workflow_name}%")
    
    if input_data.module_config:
        query += " AND mc.modins LIKE ?"
        params.append(f"%{input_data.module_config}%")
    
    # Execute the query
    cursor = ctx.deps.db_connection.cursor()
    cursor.execute(query, params)
    results = []
    
    for row in cursor.fetchall():
        result = TransformationSearchResult(
            id=row[0],
            desc=row[1],
            ord_nr=row[2],
            mic_id=row[3],
            modins=row[4],
            workflow_id=row[5],
            workflow_name=row[6],
            workflow_desc=row[7]
        )
        results.append(result)
    
    # Generate markdown content
    markdown_content = f"## Transformation Search Results\n\n"
    markdown_content += f"Found {len(results)} transformations matching the criteria.\n\n"
    
    if results:
        markdown_content += "| Workflow | Module Config | Transformation | Order | Description |\n"
        markdown_content += "|----------|---------------|----------------|-------|-------------|\n"
        
        for result in results:
            markdown_content += f"| {result.workflow_name} | {result.modins} | {result.id} | {result.ord_nr} | {result.desc} |\n"
    else:
        markdown_content += "No transformations found matching the criteria.\n"
    
    return TransformationSearchOutput(
        results=results,
        markdown_content=markdown_content
    )


@log_tool_call
async def get_transformation_details(ctx: RunContext[Deps], input: TransformationDetailsInput) -> TransformationDetailsOutput:
    """
    Get detailed information about a specific transformation, including its input and output time series.
    
    Args:
        ctx: RunContext with database connection
        input: TransformationDetailsInput containing the transformation ID
            
    Returns:
        TransformationDetailsOutput: A complete description of the transformation including:
            - Structured data about the transformation and its time series links
            - Pre-formatted markdown content for display
    """
    # Get transformation details and time series links
    query = f"""
    SELECT t.id, t.desc, t.ord_nr, t.config_file, t.mic_id, mc.modins,
           l.inout, ts.id as tss_id
    FROM trafos t
    JOIN modins_calls mc ON t.mic_id = mc.id
    LEFT JOIN links l ON t.id = l.trafo_id
    LEFT JOIN ts_sets ts ON l.tss_id = ts.id
    WHERE t.id = {input.transformation_id}
    ORDER BY l.inout, ts.id
    """
    
    result = await execute_query(ctx, SQLQueryInput(query=query))
    
    if not result.results:
        raise ModelRetry(f"No transformation found with ID {input.transformation_id}")
    
    # Group time series links by transformation
    transformation_data = {}
    for row in result.results:
        trafo_id = row['id']
        if trafo_id not in transformation_data:
            transformation_data[trafo_id] = {
                'id': row['id'],
                'desc': row['desc'],
                'ord_nr': row['ord_nr'],
                'config_file': row['config_file'],
                'mic_id': row['mic_id'],
                'modins': row['modins'],
                'time_series_links': []
            }
        
        if row['tss_id']:  # Only add if there's a time series link
            transformation_data[trafo_id]['time_series_links'].append({
                'inout': row['inout'],
                'tss_id': row['tss_id']
            })
    
    # Create markdown content
    markdown_content = f"""## Transformation Details
**ID:** {transformation_data[input.transformation_id]['id']}
**Description:** {transformation_data[input.transformation_id]['desc']}
**Config File:** {transformation_data[input.transformation_id]['config_file']}

### Basic Information
| Property | Value |
|----------|--------|
| Order Number | {transformation_data[input.transformation_id]['ord_nr']} |
| Module Instance | {transformation_data[input.transformation_id]['modins']} |
| Module Config ID | {transformation_data[input.transformation_id]['mic_id']} |

### Time Series Connections
This transformation processes the following time series:

#### Input Time Series
"""
    input_ts = [ts for ts in transformation_data[input.transformation_id]['time_series_links'] if ts['inout'] == 'in']
    output_ts = [ts for ts in transformation_data[input.transformation_id]['time_series_links'] if ts['inout'] == 'out']

    if input_ts:
        markdown_content += "| ID | Description |\n"
        markdown_content += "|----|-------------|\n"
        for ts in input_ts:
            markdown_content += f"| {ts['tss_id']} | Input time series |\n"
    else:
        markdown_content += "No input time series connected.\n"

    markdown_content += "\n#### Output Time Series\n"
    if output_ts:
        markdown_content += "| ID | Description |\n"
        markdown_content += "|----|-------------|\n"
        for ts in output_ts:
            markdown_content += f"| {ts['tss_id']} | Output time series |\n"
    else:
        markdown_content += "No output time series connected.\n"

    # Add Mermaid diagram
    markdown_content += "\n### Transformation Flow\n```mermaid\ngraph LR\n"
    
    # Add transformation node
    markdown_content += f"    T[{transformation_data[input.transformation_id]['desc']}]:::transformation\n"
    
    # Add input time series nodes and connections
    if input_ts:
        for ts in input_ts:
            markdown_content += f"    I{ts['tss_id']}[Input TS {ts['tss_id']}]:::input\n"
            markdown_content += f"    I{ts['tss_id']} --> T\n"
    
    # Add output time series nodes and connections
    if output_ts:
        for ts in output_ts:
            markdown_content += f"    O{ts['tss_id']}[Output TS {ts['tss_id']}]:::output\n"
            markdown_content += f"    T --> O{ts['tss_id']}\n"
    
    # Add styles
    markdown_content += """
    classDef transformation fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef input fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
```\n"""
    
    # Create the output using Pydantic models
    return TransformationDetailsOutput(
        results=[TransformationDetails(**transformation_data[input.transformation_id])],
        markdown_content=markdown_content
    )


@log_tool_call
async def analyze_dependencies(ctx: RunContext[Deps], input: DependencyAnalysisInput) -> DependencyAnalysisOutput:
    """
    Analyze dependencies for a specific entity, showing both upstream and downstream relationships.
    
    Args:
        ctx: RunContext with database connection
        input: DependencyAnalysisInput containing entity details and analysis direction
            
    Returns:
        DependencyAnalysisOutput: A complete description of dependencies including:
            - Structured data about the dependencies
            - Pre-formatted markdown content for display
    """
    if input.entity_type == "timeseries":
        # For time series, show both producers and consumers
        query = f"""
        WITH producers AS (
            -- Find transformations that produce this time series
            SELECT 
                t.id as trafo_id, t.desc as trafo_desc, t.ord_nr,
                mc.id as module_config_id, mc.modins as module_config,
                cs.id as workflow_id, cs.wf_id as workflow_name, cs.desc as workflow_desc,
                'out' as link_type
            FROM trafos t
            JOIN links l ON t.id = l.trafo_id
            JOIN modins_calls mc ON t.mic_id = mc.id
            JOIN call_stacks cs ON mc.call_stack_id = cs.id
            WHERE l.tss_id = {input.entity_id} AND l.inout = 'out'
        ),
        consumers AS (
            -- Find transformations that consume this time series
            SELECT 
                t.id as trafo_id, t.desc as trafo_desc, t.ord_nr,
                mc.id as module_config_id, mc.modins as module_config,
                cs.id as workflow_id, cs.wf_id as workflow_name, cs.desc as workflow_desc,
                'in' as link_type
            FROM trafos t
            JOIN links l ON t.id = l.trafo_id
            JOIN modins_calls mc ON t.mic_id = mc.id
            JOIN call_stacks cs ON mc.call_stack_id = cs.id
            WHERE l.tss_id = {input.entity_id} AND l.inout = 'in'
        )
        SELECT * FROM producers
        UNION ALL
        SELECT * FROM consumers
        ORDER BY link_type, workflow_name, ord_nr
        """
    elif input.entity_type == "transformation":
        # For transformations, show both inputs and outputs
        query = f"""
        WITH inputs AS (
            -- Find input time series
            SELECT 
                ts.id as tss_id,
                'in' as link_type
            FROM ts_sets ts
            JOIN links l ON ts.id = l.tss_id
            WHERE l.trafo_id = {input.entity_id} AND l.inout = 'in'
        ),
        outputs AS (
            -- Find output time series
            SELECT 
                ts.id as tss_id,
                'out' as link_type
            FROM ts_sets ts
            JOIN links l ON ts.id = l.tss_id
            WHERE l.trafo_id = {input.entity_id} AND l.inout = 'out'
        )
        SELECT * FROM inputs
        UNION ALL
        SELECT * FROM outputs
        ORDER BY link_type, tss_id
        """
    elif input.entity_type == "workflow":
        # For workflows, show both callers and callees
        query = f"""
        WITH callers AS (
            -- Find workflows that call this workflow
            SELECT 
                parent.id, parent.wf_id, parent.desc,
                'in' as link_type
            FROM call_stacks parent
            JOIN call_stacks child ON child.parent_id = parent.id
            WHERE child.id = {input.entity_id}
        ),
        callees AS (
            -- Find workflows called by this workflow
            SELECT 
                child.id, child.wf_id, child.desc,
                'out' as link_type
            FROM call_stacks child
            WHERE child.parent_id = {input.entity_id}
        )
        SELECT * FROM callers
        UNION ALL
        SELECT * FROM callees
        ORDER BY link_type, wf_id
        """
    else:
        logger.warning(f"analyze_dependencies called with unknown entity type: {input.entity_type}")
        raise ModelRetry(f"Unknown entity type: {input.entity_type}")
    
    result = await execute_query(ctx, SQLQueryInput(query=query))
    
    if not result.results:
        return DependencyAnalysisOutput(
            results=[],
            markdown_content=f"No dependencies found for {input.entity_type} with ID {input.entity_id}"
        )
    
    # Create markdown content based on entity type
    if input.entity_type == "timeseries":
        markdown_content = f"""## Dependencies for Time Series {input.entity_id}

### Producers
| Module Config | Transformation | Order | Workflow | Description |
|--------------|---------------|-------|----------|-------------|
"""
        for row in result.results:
            if row['link_type'] == 'out':
                markdown_content += f"| {row['module_config']} | {row['trafo_desc']} | {row['ord_nr']} | {row['workflow_name']} | {row['workflow_desc']} |\n"
        
        markdown_content += "\n### Consumers\n| Module Config | Transformation | Order | Workflow | Description |\n|--------------|---------------|-------|----------|-------------|\n"
        for row in result.results:
            if row['link_type'] == 'in':
                markdown_content += f"| {row['module_config']} | {row['trafo_desc']} | {row['ord_nr']} | {row['workflow_name']} | {row['workflow_desc']} |\n"
    
    elif input.entity_type == "transformation":
        markdown_content = f"""## Dependencies for Transformation {input.entity_id}

### Input Time Series
| Time Series ID |
|----------------|
"""
        for row in result.results:
            if row['link_type'] == 'in':
                markdown_content += f"| {row['tss_id']} |\n"
        
        markdown_content += "\n### Output Time Series\n| Time Series ID |\n|----------------|\n"
        for row in result.results:
            if row['link_type'] == 'out':
                markdown_content += f"| {row['tss_id']} |\n"
    
    else:  # workflow
        markdown_content = f"""## Dependencies for Workflow {input.entity_id}

### Callers
| Workflow ID | Name | Description |
|------------|------|-------------|
"""
        for row in result.results:
            if row['link_type'] == 'in':
                markdown_content += f"| {row['id']} | {row['wf_id']} | {row['desc']} |\n"
        
        markdown_content += "\n### Callees\n| Workflow ID | Name | Description |\n|------------|------|-------------|\n"
        for row in result.results:
            if row['link_type'] == 'out':
                markdown_content += f"| {row['id']} | {row['wf_id']} | {row['desc']} |\n"
    
    return DependencyAnalysisOutput(
        results=result.results,
        markdown_content=markdown_content
    )


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
        if hasattr(ctx.deps, 'schema') and ctx.deps.schema:
            logger.info("Using cached schema information")
            schema = ctx.deps.schema
            
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
        schema = extract_db_schema_as_dict(db_path)
        
        # Cache schema for future use
        ctx.deps.schema = schema
        
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
async def analyze_dead_points(ctx: RunContext[Deps], input: dict = None) -> DeadPointsAnalysisOutput:
    """
    Identify "dead points" in the FEWS configuration - time series sets that are 
    neither used as inputs for any transformation nor marked as endpoints.
    
    Args:
        ctx: RunContext with database connection
        input: Optional dict with parameters (include_producers=True/False)
        
    Returns:
        DeadPointsAnalysisOutput: Analysis of dead points with formatted markdown content
    """
    try:
        # Check parameters
        include_producers = input.get("include_producers", True) if input else True
        
        # Execute query to find dead points with their origins
        dead_points_query = """
        WITH dead_points AS (
            SELECT ts.id, ts.modins, ts.vtype, ts.parid, ts.qualifiers, ts.tstype, ts.timess
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
        )
        SELECT dp.*, 
               t.id as trafo_id, t.desc as trafo_desc,
               mc.id as module_config_id, mc.modins as module_config,
               cs.id as workflow_id, cs.wf_id as workflow_name
        FROM dead_points dp
        LEFT JOIN links l ON dp.id = l.tss_id AND l.inout = 'out'
        LEFT JOIN trafos t ON l.trafo_id = t.id
        LEFT JOIN modins_calls mc ON t.mic_id = mc.id
        LEFT JOIN call_stacks cs ON mc.call_stack_id = cs.id
        ORDER BY dp.modins, dp.parid
        """
        
        dead_points_result = await execute_query(ctx, SQLQueryInput(query=dead_points_query))
        
        # If no dead points found, return early
        if not dead_points_result.results:
            return DeadPointsAnalysisOutput(
                count=0,
                dead_points=[],
                module_summary=[],
                unique_modules=0,
                parameters_affected=0,
                recommendations=[
                    "No dead points found in the configuration.",
                    "All time series are either used as inputs or marked as endpoints."
                ]
            )
        
        # Convert results to DeadPoint objects
        dead_points = []
        for row in dead_points_result.results:
            dead_point = DeadPoint(
                id=row["id"],
                modins=row["modins"],
                vtype=row["vtype"],
                parid=row["parid"],
                qualifiers=row["qualifiers"],
                tstype=row["tstype"],
                timess=row["timess"]
            )
            dead_points.append(dead_point)
        
        # Analyze by module instance
        module_counts = {}
        for dp in dead_points:
            if dp.modins in module_counts:
                module_counts[dp.modins] += 1
            else:
                module_counts[dp.modins] = 1
        
        # Convert to ModuleSummary objects
        module_summary = [
            ModuleSummary(module=module, count=count)
            for module, count in sorted(module_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Get list of dead point IDs
        dead_point_ids = [dp.id for dp in dead_points]
        
        # Find transformations that produce these dead points
        producers = {}
        if include_producers and dead_point_ids:
            id_list = ", ".join(str(id) for id in dead_point_ids)
            
            producers_query = f"""
            SELECT l.tss_id, t.id AS trafo_id, t.desc AS trafo_desc, 
                  m.modins AS module_instance, m.id as module_config_id,
                  c.wf_id AS workflow_id
            FROM links l
            JOIN trafos t ON l.trafo_id = t.id
            JOIN modins_calls m ON t.mic_id = m.id
            JOIN call_stacks c ON m.call_stack_id = c.id
            WHERE l.tss_id IN ({id_list})
            AND l.inout = 'out'
            ORDER BY l.tss_id
            """
            
            producers_result = await execute_query(ctx, SQLQueryInput(query=producers_query))
            
            if producers_result.results:
                for row in producers_result.results:
                    tss_id = row["tss_id"]
                    if tss_id not in producers:
                        producers[tss_id] = []
                    producers[tss_id].append(
                        DeadPointProducer(
                            tss_id=row["tss_id"],
                            trafo_id=row["trafo_id"],
                            trafo_desc=row["trafo_desc"],
                            module_instance=row["module_instance"],
                            workflow_id=row["workflow_id"]
                        )
                    )
        
        # Analyze which module instances, parameters, and qualifiers can be removed
        dead_module_instances = set(dp.modins for dp in dead_points)
        dead_parameters = set(dp.parid for dp in dead_points)
        dead_qualifiers = set(dp.qualifiers for dp in dead_points)
        
        # Query ALL time series sets to determine which ones are exclusively used by dead points
        all_timeseries_query = """
        SELECT DISTINCT modins, parid, qualifiers
        FROM ts_sets
        """
        
        all_timeseries_result = await execute_query(ctx, SQLQueryInput(query=all_timeseries_query))
        
        # Extract all module instances, parameters, and qualifiers from active time series
        all_module_instances = set(row['modins'] for row in all_timeseries_result.results)
        all_parameters = set(row['parid'] for row in all_timeseries_result.results)
        all_qualifiers = set(row['qualifiers'] for row in all_timeseries_result.results)
        
        # Filter out the module instances, parameters, and qualifiers that are also used by active time series
        active_timeseries_query = """
        SELECT DISTINCT ts.modins, ts.parid, ts.qualifiers
        FROM ts_sets ts
        WHERE ts.id IN (
            -- TSS used as inputs for transformations
            SELECT DISTINCT tss_id 
            FROM links 
            WHERE inout = 'in'
        )
        OR ts.id IN (
            -- TSS marked as endpoints
            SELECT tss_id 
            FROM endpoints
        )
        """
        
        active_timeseries_result = await execute_query(ctx, SQLQueryInput(query=active_timeseries_query))
        
        active_module_instances = set(row['modins'] for row in active_timeseries_result.results)
        active_parameters = set(row['parid'] for row in active_timeseries_result.results)
        active_qualifiers = set(row['qualifiers'] for row in active_timeseries_result.results)
        
        # Now identify the ones that are exclusively in dead points
        exclusively_dead_module_instances = dead_module_instances - active_module_instances
        exclusively_dead_parameters = dead_parameters - active_parameters
        exclusively_dead_qualifiers = dead_qualifiers - active_qualifiers
        
        # Filter module_summary to only include exclusively dead modules
        exclusively_module_summary = [
            ms for ms in module_summary if ms.module in exclusively_dead_module_instances
        ]
        
        # Create markdown content
        markdown_content = f"""## Dead Points Analysis
Found {len(dead_points)} dead points across {len(module_counts)} modules.

### Dead Points and Their Origins
| ID | Time Series | Transformation | Module Config | Workflow |
|----|-------------|----------------|---------------|----------|
"""
        
        for dp in dead_points:
            producers_info = producers.get(dp.id, [])
            if producers_info:
                for prod in producers_info:
                    ts_desc = format_timeseries_description(dp.dict())
                    markdown_content += f"| {dp.id} | {ts_desc} | {prod.trafo_desc} | {prod.module_instance} | {prod.workflow_id} |\n"
            else:
                ts_desc = format_timeseries_description(dp.dict())
                markdown_content += f"| {dp.id} | {ts_desc} | - | - | - |\n"
        
        if exclusively_dead_module_instances:
            markdown_content += "\n### Module Instances That Can Be Removed\n"
            markdown_content += "| Module Instance | Dead Points Count |\n"
            markdown_content += "|----------------|-------------------|\n"
            for ms in exclusively_module_summary:
                markdown_content += f"| {ms.module} | {ms.count} |\n"
        else:
            markdown_content += "\n### Module Instances That Can Be Removed\n"
            markdown_content += "No module instances can be safely removed - all are used by active time series.\n"
        
        if exclusively_dead_parameters:
            markdown_content += "\n### Parameters That Can Be Removed\n"
            markdown_content += "| Parameter |\n"
            markdown_content += "|-----------|\n"
            for param in sorted(exclusively_dead_parameters):
                markdown_content += f"| {param} |\n"
        else:
            markdown_content += "\n### Parameters That Can Be Removed\n"
            markdown_content += "No parameters can be safely removed - all are used by active time series.\n"
        
        if exclusively_dead_qualifiers:
            markdown_content += "\n### Qualifiers That Can Be Removed\n"
            markdown_content += "| Qualifier |\n"
            markdown_content += "|-----------|\n"
            for qual in sorted(exclusively_dead_qualifiers):
                markdown_content += f"| {qual} |\n"
        else:
            markdown_content += "\n### Qualifiers That Can Be Removed\n"
            markdown_content += "No qualifiers can be safely removed - all are used by active time series.\n"
        
        # Update recommendations
        recommendations = [
            "Review the identified dead points to determine if they are needed",
            "Consider removing unused time series sets to simplify configuration",
            "Check if any dead points should be marked as endpoints",
            "Verify if transformations producing these time series are working as expected"
        ]
        
        if exclusively_dead_module_instances:
            recommendations.append(f"Consider removing {len(exclusively_dead_module_instances)} unused module instances that are EXCLUSIVELY used by dead points")
        
        if exclusively_dead_parameters:
            recommendations.append(f"Consider removing {len(exclusively_dead_parameters)} unused parameters that are EXCLUSIVELY used by dead points")
            
        if exclusively_dead_qualifiers:
            recommendations.append(f"Consider removing {len(exclusively_dead_qualifiers)} unused qualifiers that are EXCLUSIVELY used by dead points")
        
        # Add recommendations
        markdown_content += "\n### Recommendations\n"
        for rec in recommendations:
            markdown_content += f"- {rec}\n"
        
        return DeadPointsAnalysisOutput(
            count=len(dead_points),
            dead_points=dead_points,
            module_summary=exclusively_module_summary,  # Only include exclusively dead modules
            unique_modules=len(exclusively_dead_module_instances),  # Only count exclusively dead modules
            parameters_affected=len(exclusively_dead_parameters),  # Only count exclusively dead parameters
            producers=producers,
            recommendations=recommendations,
            markdown_content=markdown_content
        )
        
    except Exception as e:
        error_msg = f"Error analyzing dead points: {str(e)}"
        logger.error(error_msg)
        raise ModelRetry(error_msg)


async def visualize_graph(
    ctx: RunContext[Deps],
    input_data: GraphVisualizationInput
) -> GraphVisualizationOutput:
    """Generate a graph visualization of FEWS entities and their relationships.
    
    This tool creates a graph visualization starting from a root entity (time series,
    transformation, or workflow) and shows its relationships with other entities.
    The output is formatted as a Mermaid diagram in markdown.
    
    Args:
        ctx: RunContext with database connection
        input_data: Visualization parameters including root entity and layout settings
        
    Returns:
        GraphVisualizationOutput containing nodes, edges, and Mermaid markdown
    """
    # Initialize layout parameters
    layout = input_data.layout or GraphLayout()
    max_depth = layout.max_depth or 3
    max_nodes = input_data.max_nodes or 50
    
    # Initialize lists to store nodes and edges
    nodes = []
    edges = []
    node_count = 0
    
    def add_node(entity_type: str, entity_id: int, label: str, properties: Dict[str, str] = None, level: int = 0) -> bool:
        """Helper function to add a node if we haven't exceeded limits."""
        nonlocal node_count
        if node_count >= max_nodes:
            return False
            
        node = GraphNode(
            id=entity_id,
            type=entity_type,
            label=label,
            properties=properties or {},
            level=level
        )
        nodes.append(node)
        node_count += 1
        return True
    
    def add_edge(source_id: int, target_id: int, edge_type: str, label: str = None, properties: Dict[str, str] = None):
        """Helper function to add an edge."""
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            label=label,
            properties=properties or {}
        )
        edges.append(edge)
    
    async def get_time_series_node(tss_id: int, level: int = 0) -> bool:
        """Get time series node and its relationships using describe_timeseries tool."""
        # Get time series details
        time_series_result = await describe_timeseries(ctx, DescribeTimeSeriesInput(timeseries_id=tss_id))
        if not time_series_result.results:
            return False
            
        time_series = time_series_result.results[0]
        
        # Create node label and properties
        label = time_series.description
        properties = {
            "type": time_series.tstype,
            "timestep": time_series.timess
        }
        
        # Add the node
        if not add_node("timeseries", time_series.id, label, properties, level):
            return False
            
        # Get transformations if we haven't reached max depth
        if level < max_depth and time_series.transformations:
            for trans in time_series.transformations:
                # Add transformation node
                trafo_label = f"{trans.module_config}|{trans.trafo_desc}"
                if add_node("transformation", trans.trafo_id, trafo_label, {"order": str(trans.ord_nr)}, level + 1):
                    # Add edge from time series to transformation
                    add_edge(tss_id, trans.trafo_id, "used_by", f"in {trans.module_config}")
                    
                    # Get linked time series
                    if trans.linked_tss_modins:
                        linked_label = f"{trans.linked_tss_modins}|{trans.linked_tss_parid}|{trans.linked_tss_qualifiers}"
                        if add_node("timeseries", 0, linked_label, {}, level + 2):  # ID 0 for linked time series
                            add_edge(trans.trafo_id, 0, "produces", f"out {trans.module_config}")
        
        return True
    
    async def get_transformation_node(trafo_id: int, level: int = 0) -> bool:
        """Get transformation node and its relationships using get_transformation_details tool."""
        # Get transformation details
        trafo_result = await get_transformation_details(ctx, TransformationDetailsInput(transformation_id=trafo_id))
        if not trafo_result.results:
            return False
            
        trafo = trafo_result.results[0]
        
        # Create node label and properties
        label = f"{trafo.modins}|{trafo.desc}"
        properties = {
            "order": str(trafo.ord_nr)
        }
        
        # Add the node
        if not add_node("transformation", trafo.id, label, properties, level):
            return False
            
        # Get time series links if we haven't reached max depth
        if level < max_depth and trafo.time_series_links:
            for link in trafo.time_series_links:
                # Recursively get time series nodes
                if await get_time_series_node(link.tss_id, level + 1):
                    # Add appropriate edge based on direction
                    if link.inout == 'in':
                        add_edge(link.tss_id, trafo.id, "input_to", f"input {trafo.modins}")
                    else:
                        add_edge(trafo.id, link.tss_id, "produces", f"output {trafo.modins}")
        
        return True
    
    async def get_workflow_node(workflow_id: int, level: int = 0) -> bool:
        """Get workflow node and its relationships using get_workflow_details tool."""
        # Get workflow details
        workflow_result = await get_workflow_details(ctx, WorkflowDetailsInput(workflow_id=workflow_id))
        if not workflow_result.results:
            return False
            
        workflow = workflow_result.results[0]
        
        # Create node label and properties
        label = workflow.wf_id
        properties = {
            "description": workflow.desc
        }
        
        # Add the node
        if not add_node("workflow", workflow.id, label, properties, level):
            return False
            
        # Get module calls if we haven't reached max depth
        if level < max_depth and workflow.module_calls:
            for call in workflow.module_calls:
                # Recursively get transformation nodes
                if await get_transformation_node(call.mic_id, level + 1):
                    # Add edge from workflow to transformation
                    add_edge(workflow.id, call.mic_id, "contains", f"in {call.modins}")
        
        return True
    
    # Start building the graph from the root entity
    if input_data.root_entity_type == "timeseries":
        await get_time_series_node(input_data.root_entity_id)
    elif input_data.root_entity_type == "transformation":
        await get_transformation_node(input_data.root_entity_id)
    elif input_data.root_entity_type == "workflow":
        await get_workflow_node(input_data.root_entity_id)
    
    # Generate Mermaid diagram
    mermaid_lines = ["```mermaid", "graph " + layout.direction]
    
    # Add node definitions
    for node in nodes:
        # Create node label with properties if requested
        label = node.label
        if input_data.include_properties and node.properties:
            props = ", ".join(f"{k}: {v}" for k, v in node.properties.items())
            label = f"{label}<br/>({props})"
        
        # Add node with appropriate styling based on type
        style = {
            "timeseries": "fill:#e1f5fe,stroke:#01579b",
            "transformation": "fill:#f3e5f5,stroke:#4a148c",
            "workflow": "fill:#e8f5e9,stroke:#1b5e20"
        }.get(node.type, "")
        
        mermaid_lines.append(f"{node.id}[\"{label}\"]:::{style}")
    
    # Add edge definitions
    for edge in edges:
        # Create edge label with properties if requested
        label = edge.label or ""
        if input_data.include_properties and edge.properties:
            props = ", ".join(f"{k}: {v}" for k, v in edge.properties.items())
            label = f"{label} ({props})"
        
        # Add edge with appropriate styling based on type
        style = {
            "used_by": "stroke:#01579b",
            "produces": "stroke:#1b5e20",
            "contains": "stroke:#4a148c",
            "input_to": "stroke:#01579b"
        }.get(edge.type, "")
        
        mermaid_lines.append(f"{edge.source_id} -->|{label}| {edge.target_id}:::{style}")
    
    mermaid_lines.append("```")
    
    # Create markdown content
    markdown_content = "\n".join(mermaid_lines)
    
    return GraphVisualizationOutput(
        nodes=nodes,
        edges=edges,
        layout=layout,
        markdown_content=markdown_content
    ) 