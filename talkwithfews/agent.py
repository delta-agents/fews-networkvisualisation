"""
FEWS Configuration Agent.

This module defines the agent that can answer questions about FEWS configurations.
"""

import os
from pydantic_ai import Agent, Tool
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.agent import AgentRunResult

from .models import Deps

# Import logging utilities from the dedicated module
from .logging_utils import logger, setup_logging

from .tools import (
    execute_query,
    search_workflows,
    search_timeseries,
    describe_timeseries,
    search_transformations,
    get_transformation_details,
    analyze_dependencies,
    find_workflow_call_hierarchy,
    get_database_schema,
    analyze_dead_points,
    visualize_graph
)

from .utils import connect_to_database

from .schema_utils import extract_db_schema_as_dict, generate_llm_context
from .models import AgentResponse

import re

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
        
        if not db_connection:
            logger.warning("Database connection not established. Connecting now.")
            db_connection = connect_to_database(db_path)
            self.db_connection = db_connection
        
        # Set up dependencies for the agent
        deps = Deps(
            db_path=db_path,
            db_connection=db_connection
        )
        
        # Extract the database schema for the LLM
        logger.info("Extracting LLM-friendly schema information")
        schema = extract_db_schema_as_dict(db_path)
        llm_context = generate_llm_context(schema)
        
        # Set schema in deps for tools to access
        deps.schema = schema
        
        # Create a simplified system prompt with the schema information
        system_prompt = (
            "You are the FEWS Configuration Agent for analyzing Flood Early Warning System configurations. "
            f"You have access to the database schema:\n{llm_context}\n\n"
            "Your capabilities include analyzing timeseriessets, transformations, workflows, and dependencies in FEWS. "
            "Common questions are about data flows of time series sets (even when mentioned as time series, it is a time series set). "
            "Time series sets shall be formatted using using a standard template, that returns by the description argument of the describe_timeseries tool (model TimeSeriesProperties). "
            "This template is: {modins}•{vtype}•{parid}•{qualifiers (if any)}•{tstype}•{timess}\n\n"
            "Time series sets are the input and output of transformations. "
            "To trace a data flow from an endpoint inspect which transformations has it as an output. "
            "Then check which time series sets are defined as an input for these transformations, "
            "and check which transformations has these time series sets defined as input. "
            "Continue this process until you have traced the data flow to the initial imports, "
            "until the corresponding time series sets are not an output of any transformations. "
            "This way you can trace the data flow of time series sets backwards and forwards."
            "You can visualize data flows only using mermaid diagram syntax.\n\n"
            "Response Format:\n"
            "- You response shall be in Dutch\n"
            "- Use available tools to gather accurate information first\n"
            "- Include explanatory text in markdown format\n"
            "- Add tables when appropriate (markdown format)\n"
            "- Include mermaid diagrams when visualizing relationships\n\n"
            "Always structure your response with text first, followed by tables and diagrams if needed."
        )
            
        logger.info("Using comprehensive schema from schema_utils")
        # Set up the tools
        tools = [
            Tool(execute_query, takes_ctx=True, name="execute_query", description="Execute a SQL query against the FEWS configuration database"),
            Tool(search_workflows, takes_ctx=True, name="search_workflows", description="Search for workflows by name or description"),
            Tool(search_timeseries, takes_ctx=True, name="search_timeseries", description="Search for time series by parameter ID, qualifier, or module instance"),
            Tool(describe_timeseries, takes_ctx=True, name="describe_timeseries", description="Get detailed information about a specific time series"),
            Tool(search_transformations, takes_ctx=True, name="search_transformations", description="Search for transformations by description or module instance"),
            Tool(get_transformation_details, takes_ctx=True, name="get_transformation_details", description="Get detailed information about a specific transformation"),
            Tool(analyze_dependencies, takes_ctx=True, name="analyze_dependencies", description="Analyze dependencies for a specific entity, showing both upstream and downstream relationships"),
            Tool(find_workflow_call_hierarchy, takes_ctx=True, name="find_workflow_call_hierarchy", description="Trace workflow call stacks"),
            Tool(get_database_schema, takes_ctx=True, name="get_database_schema", description="Get the database schema information to understand the structure of the FEWS configuration database"),
            Tool(analyze_dead_points, takes_ctx=True, name="analyze_dead_points", description="Identify time series sets that are neither used as inputs nor marked as endpoints ('dead points')"),
            Tool(visualize_graph, takes_ctx=True, name="visualize_graph", description="Generate a graph visualization of FEWS entities and their relationships")
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
            deps_type=Deps,
            result_type=AgentResponse
        )
        
        # Store deps for later use when calling the agent
        self.deps = deps
        
        return self
    
    async def ask(self, question: str) -> "AgentRunResult":
        """
        Ask the FEWS Configuration Agent a question.
        
        Args:
            question: The question to ask
            
        Returns:
            AgentRunResult: The agent's response object containing AgentResponse in its data property
        """
        if self.agent is None:
            self.connect()
        
        logger.info(f"Asking agent: {question}")
        
        try:
            # Use basic run method
            response = await self.agent.run(question, deps=self.deps)
            return response
                        
        except Exception as e:
            logger.error(f"Error asking agent: {str(e)}")
            raise