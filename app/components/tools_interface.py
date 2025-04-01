"""
Simplified interface for FEWS configuration analysis tools.
"""
import sqlite3
import asyncio
from typing import Optional, Dict, Any
from contextlib import contextmanager
import logging

from talkwithfews.models import (
    WorkflowSearchInput,
    WorkflowSearchOutput,
    DeadPointsAnalysisOutput,
    SQLQueryInput
)

from talkwithfews.tools import (
    search_workflows,
    analyze_dead_points,
    execute_query
)


class ToolsInterface:
    """Simplified interface to the FEWS analysis tools."""
    
    def __init__(self, db_path: str):
        """
        Initialize the tools interface.
        
        Args:
            db_path: Path to the FEWS configuration database
        """
        self.db_path = db_path
        
    @contextmanager
    def _get_connection(self):
        """Get a database connection for the current thread."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _create_context(self, connection):
        """Create a context object for tool calls."""
        from pydantic_ai import RunContext
        from talkwithfews.models import Deps
        
        # Create a proper Deps object with only the expected parameters
        deps = Deps(
            db_path=self.db_path, 
            db_connection=connection
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
    
    def search_workflows(self, name_pattern: str = "%") -> WorkflowSearchOutput:
        """
        Search for workflows by name pattern.
        
        Args:
            name_pattern: SQL LIKE pattern to match workflow names/descriptions
            
        Returns:
            WorkflowSearchOutput containing matching workflows
        """
        try:
            with self._get_connection() as connection:
                ctx = self._create_context(connection)
                input_data = WorkflowSearchInput(name_pattern=name_pattern)
                
                # Create event loop and run async function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(search_workflows(ctx, input_data))
                    return result
                finally:
                    loop.close()
                
        except Exception as e:
            raise Exception(f"Error searching workflows: {str(e)}")

    def analyze_dead_points(self, include_producers: bool = True) -> DeadPointsAnalysisOutput:
        """
        Analyze dead points in the configuration.
        
        Args:
            include_producers: Whether to include information about transformations producing dead points
            
        Returns:
            DeadPointsAnalysisOutput containing analysis results
        """
        try:
            with self._get_connection() as connection:
                ctx = self._create_context(connection)
                input_data = {"include_producers": include_producers}
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(analyze_dead_points(ctx, input_data))
                    return result
                finally:
                    loop.close()
        except Exception as e:
            raise Exception(f"Error analyzing dead points: {str(e)}")

    def execute_custom_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Execute a custom SQL query."""
        try:
            with self._get_connection() as connection:
                ctx = self._create_context(connection)
                query_input = SQLQueryInput(query=query)
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(execute_query(ctx, query_input))
                    return result
                finally:
                    loop.close()
        except Exception as e:
            logging.error(f"Error executing query: {str(e)}")
            return None 