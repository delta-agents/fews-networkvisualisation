import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

import streamlit as st
from streamlit_markdown import st_markdown
from talkwithfews.agent import FEWSConfigAgent
import asyncio
from queue import Queue, Empty
import threading
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentManager:
    """Manages the FEWS agent in a separate thread"""
    def __init__(self, config):
        self.config = config
        self.agent = None
        self.response_queue = Queue()
        self.command_queue = Queue()
        self.thread = None
        self.ready = threading.Event()
        self.processing = False
        self.error = None

    def initialize(self):
        """Initialize the agent in a dedicated thread"""
        def agent_thread():
            try:
                # Create and initialize agent
                self.agent = FEWSConfigAgent(
                    db_path=self.config["db_path"],
                    log_dir=self.config["log_dir"]
                )
                self.agent.connect()
                
                # Set up event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Signal ready
                self.ready.set()
                
                while True:
                    try:
                        command = self.command_queue.get(timeout=1)
                        if command is None:  # Shutdown signal
                            break
                            
                        self.processing = True
                        self.error = None
                        
                        try:
                            response = loop.run_until_complete(asyncio.wait_for(
                                self.agent.ask(command),
                                timeout=300
                            ))
                            self.response_queue.put(response)
                        except asyncio.TimeoutError:
                            self.error = "Request timed out after 5 minutes"
                            self.response_queue.put(self.error)
                        except Exception as e:
                            self.error = str(e)
                            self.response_queue.put(f"Error: {str(e)}")
                        finally:
                            self.processing = False
                            
                    except Empty:
                        continue
                    except Exception as e:
                        self.error = str(e)
                        self.response_queue.put(f"Error: {str(e)}")
                        self.processing = False
                        
            except Exception as e:
                self.error = str(e)
                self.response_queue.put(f"Error: {str(e)}")
            finally:
                try:
                    loop.close()
                except:
                    pass
                
        self.thread = threading.Thread(target=agent_thread, daemon=True)
        self.thread.start()
        if not self.ready.wait(timeout=10):
            raise Exception("Agent initialization timed out")

    def ask(self, prompt):
        """Send a question to the agent thread"""
        if not self.thread or not self.thread.is_alive():
            raise Exception("Agent thread is not running")
            
        self.command_queue.put(prompt)
        start_time = time.time()
        
        while time.time() - start_time < 300:  # 5 minutes timeout
            try:
                # Wait for response with a short timeout
                response = self.response_queue.get(timeout=1)
                if isinstance(response, str) and response.startswith("Error:"):
                    raise Exception(response)
                return response
            except Empty:
                # If we're still processing, keep waiting
                if self.processing:
                    continue
                # If we have an error, raise it
                if self.error:
                    raise Exception(self.error)
                # Otherwise, keep waiting
                continue
                
        raise Exception("Timeout waiting for response")

    def close(self):
        """Close the agent and cleanup"""
        if self.thread and self.thread.is_alive():
            self.command_queue.put(None)
            self.thread.join(timeout=5)
        self.agent = None
        self.thread = None
        self.ready.clear()
        self.processing = False
        self.error = None

def init_chat_state():
    """Initialize chat state and agent if not exists"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_manager" not in st.session_state:
        st.session_state.agent_manager = None
    if "selected_data" not in st.session_state:
        st.session_state.selected_data = None

def format_agent_response(response):
    """Format the agent response for display"""
    if hasattr(response, 'data'):
        content = {
            "text": response.data.markdown_text or "",
            "table": response.data.markdown_table or "",
            "diagram": response.data.mermaid_diagram or ""
        }
    else:
        content = {"text": str(response), "table": "", "diagram": ""}
    return content

def add_to_chat(data: dict):
    """
    Add FEWS object data to the chat as a question and get agent response.
    
    Args:
        data: Dictionary containing FEWS object information with at least a 'type' field
            Supported types:
            - workflow: Contains Workflow ID, Beschrijving, Module Config IDs
            - timeseries: Contains ID, Module, Parameter info for timeseries
            Future support planned for:
            - transformation: Contains transformation details
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Format question based on object type
    if data.get("type") == "timeseries":
        # For timeseries sets
        ts_id = data.get("ID")
        module = data.get("Module", "")
        parameter = data.get("Parameter", "")
        question = (
            f"Kun je me meer vertellen over de tijdreeks met ID {ts_id}? "
            f"Deze tijdreeks is van parameter '{parameter}' in module '{module}'. "
            f"Wat zijn de producerende transformaties en waar wordt deze tijdreeks voor gebruikt?"
            f"Met andere woorden, waarom is dit een dood punt in de configuratie?"            
        )
    elif data.get("type") == "workflow":
        # For workflows (renamed from the default case)
        workflow_id = data.get("Workflow ID")
        if not workflow_id:
            st.error("Geen workflow ID gevonden in de data")
            return
        
        # Format the workflow data into a clear question
        question = (
            f"Kun je me meer vertellen over de workflow met ID {workflow_id}? "
            f"Deze workflow heeft als beschrijving: '{data.get('Beschrijving', 'Geen beschrijving')}' "
            f"en gebruikt de volgende Module Config IDs: {data.get('Module Config IDs', [])}"
        )
    else:
        st.error(f"Niet-ondersteund object type: {data.get('type', 'onbekend')}")
        return

    # Add the question to the chat history
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })
    
    # Store the question in session state to process after rerun
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None
    st.session_state.pending_question = question
    
    # Trigger a rerun to update the UI with the question
    st.rerun()

def show_table_dialog(table_content: str, title: str = "Table Details"):
    """Display a table in a popover."""
    with st.popover(title):
        st.markdown(table_content)
        if st.button("Close", use_container_width=True):
            st.rerun()

def format_mermaid_diagram(diagram_content: str) -> str:
    """Format the diagram content to ensure proper mermaid syntax."""
    if not diagram_content.startswith("```mermaid"):
        diagram_content = "```mermaid\n" + diagram_content
    if not diagram_content.endswith("```"):
        diagram_content = diagram_content + "\n```"
    return diagram_content

def render_chat_sidebar(config=None):
    """Render the chat interface in the sidebar"""
    # Add custom CSS for the diagram container
    st.markdown("""
        <style>
        .diagram-container {
            min-height: 400px;
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 10px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("Chat Interface")
        
        # Initialize agent if config provided
        if config and st.session_state.agent_manager is None:
            try:
                st.session_state.agent_manager = AgentManager(config)
                st.session_state.agent_manager.initialize()
            except Exception as e:
                st.error(f"Error initializing FEWS agent: {str(e)}")
                return
        
        # Display chat messages
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                content = message["content"]
                
                # Handle both string and dictionary content
                if isinstance(content, str):
                    st.markdown(content)
                else:
                    # Display text
                    if content.get("text"):
                        st.markdown(content["text"])
                    
                    # Show table and diagram popovers if available
                    if content.get("table") or content.get("diagram"):
                        cols = st.columns(2)
                        
                        # Table popover in first column if available
                        if content.get("table"):
                            with cols[0]:
                                with st.popover("📊 Table Details"):
                                    st.markdown(content["table"])
                        
                        # Diagram popover in second column if available
                        if content.get("diagram"):
                            with cols[1]:
                                with st.popover("📈 Diagram Details"):
                                    # Format and display the mermaid diagram
                                    formatted_diagram = format_mermaid_diagram(content["diagram"])
                                    st_markdown(formatted_diagram, height=380)
        
        # Process pending question if exists
        if hasattr(st.session_state, 'pending_question') and st.session_state.pending_question:
            question = st.session_state.pending_question
            st.session_state.pending_question = None  # Clear the pending question
            
            # Get agent response if available
            if st.session_state.agent_manager:
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.agent_manager.ask(question)
                        content = format_agent_response(response)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": content
                        })
                    except Exception as e:
                        st.error(str(e))
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": {"text": f"Error: {str(e)}"}
                        })
                st.rerun()  # Update UI with the response
        
        # Chat input
        if prompt := st.chat_input("Ask about FEWS configuration..."):
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Store as pending question
            st.session_state.pending_question = prompt
            st.rerun()
        
        # Cleanup button
        if st.button("End Session", use_container_width=True):
            if st.session_state.agent_manager:
                st.session_state.agent_manager.close()
            st.session_state.agent_manager = None
            st.session_state.messages = []
            st.session_state.pending_question = None
            st.rerun() 