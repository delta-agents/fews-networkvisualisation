"""
Visualization tools for the FEWS Configuration Agent.

This module provides tools for generating visualizations of FEWS configurations.
"""

from pydantic_ai import RunContext, ModelRetry

from .models import (
    Deps,
    SQLQueryInput,
    VisualizationRequestInput
)

from .tools import execute_query
from .utils import generate_mermaid_diagram
from .logging_utils import log_tool_call, logger


@log_tool_call
async def generate_network_visualization(ctx: RunContext[Deps], input: VisualizationRequestInput) -> str:
    """
    Generate a network diagram of relationships.
    
    Args:
        ctx: RunContext with database connection
        input: VisualizationRequestInput containing entity details
        
    Returns:
        str: Mermaid diagram code
    """
    if input.entity_type == "timeseries":
        # Visualize a time series and its related transformations
        query = f"""
        WITH upstream AS (
            SELECT t.id, t.desc, 'produces' as relationship
            FROM trafos t
            JOIN links l ON t.id = l.trafo_id
            WHERE l.tss_id = {input.entity_id} AND l.inout = 'out'
        ),
        downstream AS (
            SELECT t.id, t.desc, 'consumes' as relationship
            FROM trafos t
            JOIN links l ON t.id = l.trafo_id
            WHERE l.tss_id = {input.entity_id} AND l.inout = 'in'
        ),
        ts_info AS (
            SELECT id, modins, parid, qualifiers, tstype
            FROM ts_sets
            WHERE id = {input.entity_id}
        ),
        endpoint_info AS (
            SELECT e.desc
            FROM endpoints e
            WHERE e.tss_id = {input.entity_id}
        )
        SELECT 
            t.id as trafo_id, 
            t.desc as trafo_desc, 
            t.relationship,
            ts.id as tss_id, 
            ts.parid, 
            ts.qualifiers,
            e.desc as endpoint_desc
        FROM 
            (SELECT * FROM upstream UNION ALL SELECT * FROM downstream) t
        CROSS JOIN ts_info ts
        LEFT JOIN endpoint_info e ON 1=1
        """
        
        results = await execute_query(ctx, SQLQueryInput(query=query))
        
        # Generate the Mermaid diagram
        diagram = "```mermaid\nflowchart LR\n"
        
        # Add the time series node
        if results.results:
            ts_id = f"TS{results.results[0]['tss_id']}"
            ts_label = f"{results.results[0]['parid']}"
            if results.results[0]['qualifiers']:
                ts_label += f" ({results.results[0]['qualifiers']})"
            
            diagram += f"  {ts_id}[{ts_label}]\n"
            
            # Add endpoint if it exists
            if results.results[0]['endpoint_desc']:
                endpoint_id = f"EP{results.results[0]['tss_id']}"
                endpoint_label = f"Endpoint: {results.results[0]['endpoint_desc']}"
                
                diagram += f"  {endpoint_id}[{endpoint_label}]\n"
                diagram += f"  {ts_id} --> {endpoint_id}\n"
            
            # Add transformation nodes and relationships
            for row in results.results:
                trafo_id = f"T{row['trafo_id']}"
                trafo_label = row['trafo_desc']
                
                diagram += f"  {trafo_id}[{trafo_label}]\n"
                
                if row['relationship'] == 'produces':
                    diagram += f"  {trafo_id} --> {ts_id}\n"
                else:
                    diagram += f"  {ts_id} --> {trafo_id}\n"
        
        diagram += "```"
        
        logger.info(f"Generated network visualization for timeseries ID {input.entity_id} with {len(results.results) if results.results else 0} relationships")
        return diagram
    
    elif input.entity_type == "transformation":
        # Visualize a transformation and its inputs/outputs
        query = f"""
        WITH t_info AS (
            SELECT t.id, t.desc, t.mic_id, mc.modins, cs.id as call_stack_id, cs.wf_id
            FROM trafos t
            JOIN modins_calls mc ON t.mic_id = mc.id
            JOIN call_stacks cs ON mc.call_stack_id = cs.id
            WHERE t.id = {input.entity_id}
        ),
        inputs AS (
            SELECT ts.id, ts.parid, ts.qualifiers, 'in' as inout
            FROM ts_sets ts
            JOIN links l ON ts.id = l.tss_id
            WHERE l.trafo_id = {input.entity_id} AND l.inout = 'in'
        ),
        outputs AS (
            SELECT ts.id, ts.parid, ts.qualifiers, 'out' as inout
            FROM ts_sets ts
            JOIN links l ON ts.id = l.tss_id
            WHERE l.trafo_id = {input.entity_id} AND l.inout = 'out'
        )
        SELECT 
            t.id as trafo_id, 
            t.desc as trafo_desc, 
            t.modins,
            t.wf_id,
            ts.id as tss_id, 
            ts.parid, 
            ts.qualifiers,
            ts.inout
        FROM 
            t_info t
        CROSS JOIN (SELECT * FROM inputs UNION ALL SELECT * FROM outputs) ts
        """
        
        results = await execute_query(ctx, SQLQueryInput(query=query))
        
        # Generate the Mermaid diagram
        diagram = "```mermaid\nflowchart LR\n"
        
        # Add the module and workflow context
        if results.results:
            workflow_id = f"WF{results.results[0]['wf_id']}"
            workflow_label = results.results[0]['wf_id']
            
            modins_id = f"MOD{results.results[0]['modins']}"
            modins_label = results.results[0]['modins']
            
            trafo_id = f"T{results.results[0]['trafo_id']}"
            trafo_label = results.results[0]['trafo_desc']
            
            diagram += f"  {workflow_id}[{workflow_label}]\n"
            diagram += f"  {modins_id}[{modins_label}]\n"
            diagram += f"  {trafo_id}[{trafo_label}]\n"
            
            diagram += f"  {workflow_id} --> {modins_id}\n"
            diagram += f"  {modins_id} --> {trafo_id}\n"
            
            # Add time series nodes and relationships
            for row in results.results:
                tss_id = f"TS{row['tss_id']}"
                tss_label = row['parid']
                if row['qualifiers']:
                    tss_label += f" ({row['qualifiers']})"
                
                diagram += f"  {tss_id}[{tss_label}]\n"
                
                if row['inout'] == 'in':
                    diagram += f"  {tss_id} --> {trafo_id}\n"
                else:
                    diagram += f"  {trafo_id} --> {tss_id}\n"
        
        diagram += "```"
        
        logger.info(f"Generated network visualization for transformation ID {input.entity_id} with {len(results.results) if results.results else 0} connections")
        return diagram
    
    elif input.entity_type == "workflow":
        # Visualize a workflow and its module instances
        query = f"""
        WITH workflow AS (
            SELECT id, wf_id, desc, parent_id
            FROM call_stacks
            WHERE id = {input.entity_id}
        ),
        parent_workflow AS (
            SELECT id, wf_id, desc
            FROM call_stacks
            WHERE id = (SELECT parent_id FROM workflow WHERE parent_id IS NOT NULL)
        ),
        child_workflows AS (
            SELECT id, wf_id, desc
            FROM call_stacks
            WHERE parent_id = {input.entity_id}
        ),
        module_instances AS (
            SELECT mc.id, mc.modins, COUNT(t.id) as trafo_count
            FROM modins_calls mc
            LEFT JOIN trafos t ON mc.id = t.mic_id
            WHERE mc.call_stack_id = {input.entity_id}
            GROUP BY mc.id, mc.modins
        )
        
        SELECT 
            w.id as workflow_id,
            w.wf_id,
            w.desc,
            'workflow' as entity_type
        FROM 
            workflow w
        
        UNION ALL
        
        SELECT 
            p.id as workflow_id,
            p.wf_id,
            p.desc,
            'parent' as entity_type
        FROM 
            parent_workflow p
        
        UNION ALL
        
        SELECT 
            c.id as workflow_id,
            c.wf_id,
            c.desc,
            'child' as entity_type
        FROM 
            child_workflows c
        
        UNION ALL
        
        SELECT 
            m.id as workflow_id,
            m.modins as wf_id,
            CAST(m.trafo_count as TEXT) as desc,
            'module' as entity_type
        FROM 
            module_instances m
        """
        
        results = await execute_query(ctx, SQLQueryInput(query=query))
        
        # Generate the Mermaid diagram
        diagram = "```mermaid\nflowchart TB\n"
        
        # Process the results and build the diagram
        main_workflow_id = None
        parent_workflow_id = None
        
        # First pass: create nodes
        for row in results.results:
            entity_id = f"{row['entity_type'][0:1].upper()}{row['workflow_id']}"
            
            if row['entity_type'] == 'workflow':
                main_workflow_id = entity_id
                label = f"{row['wf_id']}: {row['desc']}"
                diagram += f"  {entity_id}[{label}]\n"
            
            elif row['entity_type'] == 'parent':
                parent_workflow_id = entity_id
                label = f"{row['wf_id']}: {row['desc']}"
                diagram += f"  {entity_id}[{label}]\n"
            
            elif row['entity_type'] == 'child':
                label = f"{row['wf_id']}: {row['desc']}"
                diagram += f"  {entity_id}[{label}]\n"
            
            elif row['entity_type'] == 'module':
                label = f"{row['wf_id']} ({row['desc']} transformations)"
                diagram += f"  {entity_id}({label})\n"
        
        # Second pass: create relationships
        for row in results.results:
            entity_id = f"{row['entity_type'][0:1].upper()}{row['workflow_id']}"
            
            if row['entity_type'] == 'child' and main_workflow_id:
                diagram += f"  {main_workflow_id} --> {entity_id}\n"
            
            elif row['entity_type'] == 'module' and main_workflow_id:
                diagram += f"  {main_workflow_id} --> {entity_id}\n"
        
        # Add parent relationship if it exists
        if parent_workflow_id and main_workflow_id:
            diagram += f"  {parent_workflow_id} --> {main_workflow_id}\n"
        
        diagram += "```"
        
        logger.info(f"Generated network visualization for workflow ID {input.entity_id} with {len(results.results) if results.results else 0} components")
        return diagram
    
    else:
        error_msg = f"Unsupported entity type for visualization: {input.entity_type}"
        logger.error(error_msg)
        raise ModelRetry(error_msg)


@log_tool_call
async def generate_call_hierarchy_visualization(ctx: RunContext[Deps], input: VisualizationRequestInput) -> str:
    """
    Generate a visualization of workflow call hierarchy.
    
    Args:
        ctx: RunContext with database connection
        input: VisualizationRequestInput containing entity details
        
    Returns:
        str: Mermaid diagram code
    """
    if input.entity_type != "workflow":
        error_msg = "Call hierarchy visualization is only supported for workflows"
        logger.error(error_msg)
        raise ModelRetry(error_msg)
    
    # Query to get the workflow call hierarchy
    query = f"""
    WITH RECURSIVE workflow_hierarchy AS (
        SELECT id, wf_id, desc, parent_id, 0 AS level
        FROM call_stacks
        WHERE id = {input.entity_id}
        
        UNION ALL
        
        SELECT cs.id, cs.wf_id, cs.desc, cs.parent_id, wh.level + 1
        FROM call_stacks cs
        JOIN workflow_hierarchy wh ON cs.parent_id = wh.id
        WHERE cs.parent_id IS NOT NULL
        AND wh.level < {input.depth}
    )
    SELECT id, wf_id, desc, parent_id, level
    FROM workflow_hierarchy
    ORDER BY level, wf_id
    """
    
    results = await execute_query(ctx, SQLQueryInput(query=query))
    
    # Generate the diagram
    diagram = generate_mermaid_diagram(results.results, "workflow_hierarchy")
    
    logger.info(f"Generated call hierarchy visualization for workflow ID {input.entity_id} with depth {input.depth}")
    return diagram


@log_tool_call
async def generate_data_flow_visualization(ctx: RunContext[Deps], input: VisualizationRequestInput) -> str:
    """
    Generate a visualization of data flow through transformations.
    
    Args:
        ctx: RunContext with database connection
        input: VisualizationRequestInput containing entity details
        
    Returns:
        str: Mermaid diagram code
    """
    if input.entity_type not in ["timeseries", "transformation"]:
        error_msg = "Data flow visualization is only supported for timeseries and transformations"
        logger.error(error_msg)
        raise ModelRetry(error_msg)
    
    if input.entity_type == "timeseries":
        # Query to get the data flow for a timeseries
        query = f"""
        WITH RECURSIVE data_flow AS (
            -- Start with the target timeseries
            SELECT ts.id as tss_id, ts.parid, ts.qualifiers, 0 AS level, ts.id as start_id
            FROM ts_sets ts
            WHERE ts.id = {input.entity_id}
            
            UNION ALL
            
            -- Follow upstream transformations and their inputs
            SELECT ts_in.id as tss_id, ts_in.parid, ts_in.qualifiers, df.level + 1, df.start_id
            FROM data_flow df
            JOIN links l_out ON df.tss_id = l_out.tss_id AND l_out.inout = 'out'
            JOIN trafos t ON l_out.trafo_id = t.id
            JOIN links l_in ON t.id = l_in.trafo_id AND l_in.inout = 'in'
            JOIN ts_sets ts_in ON l_in.tss_id = ts_in.id
            WHERE df.level < {input.depth}
        )
        SELECT df.tss_id, df.parid, df.qualifiers, df.level,
               t.id as trafo_id, t.desc as trafo_desc, l.inout
        FROM data_flow df
        LEFT JOIN links l ON df.tss_id = l.tss_id
        LEFT JOIN trafos t ON l.trafo_id = t.id
        WHERE t.id IS NOT NULL
        ORDER BY df.level, df.tss_id, l.inout
        """
        
        results = await execute_query(ctx, SQLQueryInput(query=query))
        
        # Generate the diagram
        diagram = generate_mermaid_diagram(results.results, "transformation_flow")
        
        logger.info(f"Generated data flow visualization for timeseries ID {input.entity_id} with depth {input.depth} and {len(results.results) if results.results else 0} nodes")
        return diagram
    
    else:  # transformation
        # Query to get the data flow for a transformation
        query = f"""
        WITH RECURSIVE data_flow AS (
            -- Start with the target transformation's inputs
            SELECT ts.id as tss_id, ts.parid, ts.qualifiers, t.id as trafo_id, t.desc as trafo_desc, 0 AS level
            FROM trafos t
            JOIN links l ON t.id = l.trafo_id AND l.inout = 'in'
            JOIN ts_sets ts ON l.tss_id = ts.id
            WHERE t.id = {input.entity_id}
            
            UNION ALL
            
            -- Follow outputs and downstream transformations
            SELECT ts_out.id as tss_id, ts_out.parid, ts_out.qualifiers, t_next.id as trafo_id, t_next.desc as trafo_desc, df.level + 1
            FROM data_flow df
            JOIN links l_in ON df.tss_id = l_in.tss_id AND l_in.inout = 'in'
            JOIN trafos t_curr ON l_in.trafo_id = t_curr.id
            JOIN links l_out ON t_curr.id = l_out.trafo_id AND l_out.inout = 'out'
            JOIN ts_sets ts_out ON l_out.tss_id = ts_out.id
            JOIN links l_next ON ts_out.id = l_next.tss_id AND l_next.inout = 'in'
            JOIN trafos t_next ON l_next.trafo_id = t_next.id
            WHERE df.level < {input.depth}
        )
        SELECT df.tss_id, df.parid, df.qualifiers, df.trafo_id, df.trafo_desc, df.level
        FROM data_flow df
        ORDER BY df.level, df.trafo_id, df.tss_id
        """
        
        results = await execute_query(ctx, SQLQueryInput(query=query))
        
        # Generate the diagram
        diagram = generate_mermaid_diagram(results.results, "transformation_flow")
        
        logger.info(f"Generated data flow visualization for transformation ID {input.entity_id} with depth {input.depth} and {len(results.results) if results.results else 0} nodes")
        return diagram 