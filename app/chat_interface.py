"""
Chat interface components for the FEWS chat application.
"""
import streamlit as st
import asyncio
from talkwithfews.agent import FEWSConfigAgent
import threading
from queue import Queue, Empty
import time
from streamlit_flow import streamlit_flow
from streamlit_flow.state import StreamlitFlowState
from uuid import uuid4

class AgentManager:
    def __init__(self, config):
        self.config = config
        self.agent = None
        self.response_queue = Queue()
        self.command_queue = Queue()
        self.thread = None
        self.ready = threading.Event()
        self.processing = False
        self.error = None  # Add error tracking

    def initialize(self):
        """Initialize the agent in a dedicated thread."""
        def agent_thread():
            try:
                # Create and initialize the agent in this thread
                self.agent = FEWSConfigAgent(
                    db_path=self.config["db_path"],
                    log_dir=self.config["log_dir"]
                )
                self.agent.connect()
                
                # Set up event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Signal that the agent is ready
                self.ready.set()
                
                while True:
                    try:
                        # Get command from queue with timeout
                        command = self.command_queue.get(timeout=1)
                        if command is None:  # Shutdown signal
                            break
                            
                        prompt = command
                        self.processing = True
                        self.error = None  # Reset error state
                        
                        # Run the async call in this thread with timeout
                        try:
                            response = loop.run_until_complete(asyncio.wait_for(
                                self.agent.ask(prompt),
                                timeout=300  # 5 minutes timeout for the API call
                            ))
                            self.response_queue.put(response)
                        except asyncio.TimeoutError:
                            self.error = "Verzoek is verlopen na 5 minuten"
                            self.response_queue.put("Fout: Verzoek is verlopen na 5 minuten")
                        except Exception as e:
                            self.error = str(e)
                            self.response_queue.put(f"Fout: {str(e)}")
                    except Empty:
                        continue  # No command, keep waiting
                    except Exception as e:
                        self.processing = False
                        self.error = str(e)
                        self.response_queue.put(f"Fout: {str(e)}")
            except Exception as e:
                self.error = str(e)
                self.response_queue.put(f"Fout: {str(e)}")
                self.processing = False
            finally:
                try:
                    loop.close()
                except:
                    pass
        
        self.thread = threading.Thread(target=agent_thread, daemon=True)
        self.thread.start()
        # Wait for the agent to be ready
        if not self.ready.wait(timeout=10):
            raise Exception("Agent kon niet worden geïnitialiseerd binnen 10 seconden")

    def ask(self, prompt):
        """Send a question to the agent thread."""
        if not self.thread or not self.thread.is_alive():
            raise Exception("Agent thread draait niet")
            
        self.command_queue.put(prompt)
        try:
            # Wait for response with timeout and processing check
            start_time = time.time()
            while time.time() - start_time < 300:  # 5 minutes timeout
                try:
                    response = self.response_queue.get(timeout=1)
                    if isinstance(response, dict):
                        return response
                    elif isinstance(response, str):
                        if response.startswith("Fout:"):
                            raise Exception(response)
                        return response
                    else:
                        return str(response)
                except Empty:
                    if not self.processing:
                        if self.error:
                            raise Exception(self.error)
                        raise Exception("Agent stopte met verwerken zonder antwoord")
                    continue
            raise Exception("Timeout wachtend op antwoord (5 minuten)")
        except Exception as e:
            raise Exception(f"Fout bij ophalen antwoord: {str(e)}")

    def close(self):
        """Close the agent and cleanup."""
        if self.thread and self.thread.is_alive():
            # Send shutdown signal
            self.command_queue.put(None)
            self.thread.join(timeout=5)
        
        self.agent = None
        self.thread = None
        self.ready.clear()
        self.processing = False
        self.error = None

    def process_agent(self):
        """Process agent responses in a separate thread."""
        while True:
            try:
                command = self.command_queue.get()
                if command is None:
                    break
                    
                self.processing = True
                self.error = None
                
                try:
                    response = asyncio.run(self.agent.ask(command))
                    if isinstance(response, dict):
                        self.response_queue.put(response)
                    else:
                        self.response_queue.put(str(response))
                except Exception as e:
                    self.error = str(e)
                    self.response_queue.put(f"Fout: {str(e)}")
                finally:
                    self.processing = False
                    
            except Exception as e:
                self.error = str(e)
                self.response_queue.put(f"Fout: {str(e)}")
                self.processing = False

def initialize_chat_history():
    """Initialize chat history in session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_manager" not in st.session_state:
        st.session_state.agent_manager = None

def render_chat_interface(config):
    """Render the chat interface."""
    initialize_chat_history()
    
    # Initialize agent if not already done
    if st.session_state.agent_manager is None:
        try:
            st.session_state.agent_manager = AgentManager(config)
            st.session_state.agent_manager.initialize()
        except Exception as e:
            st.error(f"Fout bij initialiseren FEWS agent: {str(e)}")
            return
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"]
            if isinstance(content, dict):
                # Handle special content types
                if content.get("type") == "streamlit_flow":
                    # Initialize flow state if not exists
                    flow_key = f"flow_{message['id']}"
                    if flow_key not in st.session_state:
                        st.session_state[flow_key] = content["state"]
                    
                    # Render the flow diagram
                    st.session_state[flow_key] = streamlit_flow(
                        flow_key,
                        st.session_state[flow_key]
                    )
                elif content.get("type") == "table":
                    st.table(content["data"])
                else:
                    st.markdown(content.get("text", ""))
            else:
                st.markdown(content)
    
    # Chat input
    if prompt := st.chat_input("Stel een vraag over je FEWS configuratie..."):
        # Generate unique message ID
        message_id = str(uuid4())
        
        # Add user message to chat history
        st.session_state.messages.append({
            "id": message_id,
            "role": "user",
            "content": prompt
        })
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Denken..."):
                try:
                    response = st.session_state.agent_manager.ask(prompt)
                    
                    # Handle different response types
                    if isinstance(response, dict):
                        if response.get("type") == "streamlit_flow":
                            # Store flow state in session
                            flow_key = f"flow_{message_id}"
                            if flow_key not in st.session_state:
                                st.session_state[flow_key] = response["state"]
                            
                            # Add to chat history with special content type
                            st.session_state.messages.append({
                                "id": message_id,
                                "role": "assistant",
                                "content": {
                                    "type": "streamlit_flow",
                                    "state": st.session_state[flow_key]
                                }
                            })
                            
                            # Render the flow diagram
                            streamlit_flow(
                                flow_key,
                                st.session_state[flow_key]
                            )
                        elif response.get("type") == "table":
                            st.table(response["data"])
                            st.session_state.messages.append({
                                "id": message_id,
                                "role": "assistant",
                                "content": response
                            })
                    else:
                        st.markdown(response)
                        st.session_state.messages.append({
                            "id": message_id,
                            "role": "assistant",
                            "content": response
                        })
                except Exception as e:
                    error_msg = str(e)
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "id": message_id,
                        "role": "assistant",
                        "content": error_msg
                    })
    
    # Cleanup on session end
    if st.button("Sessie Beëindigen"):
        if st.session_state.agent_manager:
            st.session_state.agent_manager.close()
        st.session_state.agent_manager = None
        st.session_state.messages = []
        st.rerun()
