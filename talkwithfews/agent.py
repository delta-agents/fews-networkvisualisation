"""
FEWS Configuration Agent.

This module defines the agent that can answer questions about FEWS configurations.
"""

import os
import json
from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .models import (
    Deps,
    ToolCallTracker
)

# Import logging utilities from the dedicated module
from .logging_utils import logger, setup_logging

from .tools import (
    execute_query,
    explain_query,
    search_workflows,
    get_workflow_details,
    search_timeseries,
    get_timeseries_details,
    search_transformations,
    get_transformation_details,
    analyze_upstream_dependencies,
    analyze_downstream_dependencies,
    find_workflow_call_hierarchy,
    get_database_schema,
    analyze_dead_points
)

from .visualization import (
    generate_network_visualization,
    generate_call_hierarchy_visualization,
    generate_data_flow_visualization
)

from .utils import connect_to_database, format_results_as_table, generate_mermaid_diagram

from .schema_utils import extract_llm_friendly_schema, generate_llm_context, create_schema_info_dict, get_table_relationships

# Create a global tracker instance for the decorator to use
tracker = ToolCallTracker()

class FEWSConfigAgent:
    """
    Agent for querying and analyzing FEWS configurations.
    """
    
    def __init__(
        self,
        db_path: str,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        log_level: str = "INFO",
        log_dir: str = None
    ):
        """
        Initialize the FEWS Configuration Agent.
        
        Args:
            db_path: Path to the SQLite database containing FEWS configuration data
            model: Optional model to use (defaults to PRIMARY_MODEL env var or gpt-4)
            api_key: Optional API key (will use OPENROUTER_API_KEY env var if not provided)
            base_url: Optional base URL (will use OPENROUTER_BASE_URL env var if not provided)
            log_level: Logging level (default is INFO)
            log_dir: Directory where log files will be stored (default is ~/.fews_agent/logs)
        """
        self.db_path = db_path
        
        # Read model name from PRIMARY_MODEL env var if available
        primary_model = os.environ.get("PRIMARY_MODEL")
        default_model = "gpt-4"
        
        if primary_model:
            logger.info(f"Using model from PRIMARY_MODEL env: {primary_model}")
            default_model = primary_model
        
        self.model_name = model or default_model
        self.api_key = api_key
        self.base_url = base_url
        self.agent = None
        self.db_connection = None
        
        # Set up logging
        setup_logging(log_level=log_level, log_dir=log_dir)
        
        # Initialize the tracking system
        self.tracker = ToolCallTracker()
        
        logger.info(f"Initialized FEWSConfigAgent with database: {db_path}")
        logger.info(f"Using model: {self.model_name}")
        if log_dir:
            logger.info(f"Logging to directory: {log_dir}")
    
    def __enter__(self):
        """Connect to database and create agent when entering context manager."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection when exiting context manager."""
        self.close()
    
    def connect(self):
        """Connect to the database and create the agent."""
        if self.db_connection is None:
            logger.info(f"Connecting to database: {self.db_path}")
            self.db_connection = connect_to_database(self.db_path)
            
            # Create the agent
            self._create_agent()
        
        return self
    
    def close(self):
        """Close the database connection."""
        if self.db_connection is not None:
            logger.info("Closing database connection")
            self.db_connection.close()
            self.db_connection = None
    
    def _create_agent(self):
        """Create the FEWS Configuration Agent with tools."""
        if self.agent is not None:
            return

        db_path = self.db_path
        db_connection = self.db_connection
        tracker = self.tracker
        
        if not db_connection:
            logger.warning("Database connection not established. Connecting now.")
            db_connection = connect_to_database(db_path)
            self.db_connection = db_connection
        
        # Set up dependencies for the agent
        deps = Deps(
            db_path=db_path,
            db_connection=db_connection,
            tracker=tracker
        )
        
        # Extract the database schema for the LLM
        logger.info("Extracting LLM-friendly schema information")
        schema = extract_llm_friendly_schema(db_path)
        llm_context = generate_llm_context(schema)
        
        # Set schema in deps for tools to access
        deps.schema = schema
        
        # Create a comprehensive system prompt with the schema information
        system_prompt = (
            "You are the FEWS Configuration Agent, providing technical analysis of FEWS configuration workflows "
            "stored in SQLite databases. Users are domain experts who need concise, structured information.\n\n"
            "You have access to the following tables in the database:\n"
            f"{llm_context}\n\n"
            "FORMAT YOUR RESPONSES IN A STRUCTURED WAY:\n"
            "1. Present query results in tables whenever possible\n"
            "2. Use diagrams to show relationships and data flows\n"
            "3. Provide key metrics and counts at the beginning of responses\n"
            "4. Structure insights with headers and bullet points\n\n"
            "Avoid conversational language. Be direct and technical. Users are experts looking for insights, not conversation.\n\n"
            "Always use the available tools to query the database and explore the configuration thoroughly before answering.\n\n"
            "IMPORTANT: For each tool you use, provide a brief reasoning about why you're using it, starting with 'Reasoning: '."
        )
            
        logger.info("Using comprehensive schema from schema_utils")
        
        # Callback to capture reasoning
        def reasoning_callback(tool_name, **kwargs):
            if 'name' in kwargs and 'thoughts' in kwargs:
                # Get reasoning from thoughts
                thoughts = kwargs.get('thoughts', '')
                if thoughts and hasattr(tracker, 'set_reasoning'):
                    # Look for reasoning in thoughts
                    reasoning_lines = [line for line in thoughts.split('\n') 
                                     if line.startswith('Reasoning:')]
                    if reasoning_lines:
                        reasoning = reasoning_lines[0].replace('Reasoning:', '').strip()
                        tracker.set_reasoning(reasoning)
                        logger.info(f"Agent reasoning for {tool_name}: {reasoning}")
        
        # Set up the tools
        tools = [
            Tool(execute_query, takes_ctx=True, name="execute_query", description="Execute a SQL query against the FEWS configuration database"),
            Tool(explain_query, takes_ctx=True, name="explain_query", description="Explain what a SQL query does without executing it"),
            Tool(search_workflows, takes_ctx=True, name="search_workflows", description="Search for workflows by name or description"),
            Tool(get_workflow_details, takes_ctx=True, name="get_workflow_details", description="Get detailed information about a specific workflow"),
            Tool(search_timeseries, takes_ctx=True, name="search_timeseries", description="Search for time series by parameter ID, qualifier, or other attributes"),
            Tool(get_timeseries_details, takes_ctx=True, name="get_timeseries_details", description="Get detailed information about a specific time series"),
            Tool(search_transformations, takes_ctx=True, name="search_transformations", description="Search for transformations by description or module instance"),
            Tool(get_transformation_details, takes_ctx=True, name="get_transformation_details", description="Get detailed information about a specific transformation"),
            Tool(analyze_upstream_dependencies, takes_ctx=True, name="analyze_upstream_dependencies", description="Find what produces a specific entity"),
            Tool(analyze_downstream_dependencies, takes_ctx=True, name="analyze_downstream_dependencies", description="Find what consumes a specific entity"),
            Tool(find_workflow_call_hierarchy, takes_ctx=True, name="find_workflow_call_hierarchy", description="Trace workflow call stacks"),
            Tool(get_database_schema, takes_ctx=True, name="get_database_schema", description="Get the database schema information to understand the structure of the FEWS configuration database"),
            Tool(analyze_dead_points, takes_ctx=True, name="analyze_dead_points", description="Identify time series sets that are neither used as inputs nor marked as endpoints ('dead points')"),
            Tool(generate_network_visualization, takes_ctx=True, name="generate_network_visualization", description="Generate a network visualization of entities and their relationships"),
            Tool(generate_call_hierarchy_visualization, takes_ctx=True, name="generate_call_hierarchy_visualization", description="Generate a visualization of workflow call hierarchy"),
            Tool(generate_data_flow_visualization, takes_ctx=True, name="generate_data_flow_visualization", description="Generate a visualization of data flow through transformations")
        ]
        
        # Create the model with OpenRouter configuration
        api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        base_url = self.base_url or os.environ.get("OPENROUTER_BASE_URL")

        if not api_key:
            raise ValueError(
                "API key not provided. Either pass as api_key parameter or set OPENROUTER_API_KEY environment variable."
            )
            
        if not base_url:
            logger.warning("No base_url provided. Using OpenAI API directly. Set OPENROUTER_BASE_URL for custom API.")

        # Update to match the template structure
        model = OpenAIModel(
            model_name=self.model_name,
            provider=OpenAIProvider(
                base_url=base_url, 
                api_key=api_key
            )
        )
        
        # Create the agent
        logger.info(f"Creating FEWS Configuration Agent using {self.model_name}")
        if base_url:
            logger.info(f"Using custom base URL: {base_url}")
            
        self.agent = Agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            deps_type=Deps
        )
        
        # Store deps for later use when calling the agent
        self.deps = deps
        
        return self
    
    async def ask(self, question: str) -> str:
        """
        Ask the FEWS Configuration Agent a question.
        
        Args:
            question: The question to ask
            
        Returns:
            str: The agent's response
        """
        if self.agent is None:
            self.connect()
        
        logger.info(f"Asking agent: {question}")
        
        # Initialize a new tracker for this question
        self.tracker = ToolCallTracker()
        
        try:
            # Pass deps when calling the agent
            response = await self.agent.run(question, deps=self.deps)
            
            # Log summary of tool calls if available
            if hasattr(self.tracker, 'get_summary'):
                tool_summary = self.tracker.get_summary()
                if tool_summary:
                    logger.info(f"Tool usage summary: {json.dumps(tool_summary, indent=2)}")
            
            return response.data
        except Exception as e:
            logger.error(f"Error asking agent: {str(e)}")
            raise


async def run_fews_agent(
    db_path: str,
    question: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
    log_level: str = "INFO",
    log_dir: str = None
) -> str:
    """
    Run the FEWS Configuration Agent on a question.
    
    Args:
        db_path: Path to the SQLite database containing FEWS configuration data
        question: The question to ask the agent
        model: Optional model to use (defaults to GPT-4)
        api_key: Optional API key (will use OPENROUTER_API_KEY env var if not provided)
        base_url: Optional base URL (will use OPENROUTER_BASE_URL env var if not provided)
        log_level: Logging level (default is INFO)
        log_dir: Directory where log files will be stored (default is ~/.fews_agent/logs)
        
    Returns:
        str: The agent's response
    """
    # Use the FEWSConfigAgent class
    async with FEWSConfigAgent(
        db_path=db_path, 
        model=model, 
        api_key=api_key, 
        base_url=base_url, 
        log_level=log_level,
        log_dir=log_dir
    ) as agent:
        return await agent.ask(question) 