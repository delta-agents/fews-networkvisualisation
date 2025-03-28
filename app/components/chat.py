"""
Chat interface components for the FEWS chat application.
"""
import streamlit as st
import asyncio
from talkwithfews.agent import FEWSConfigAgent
import threading
from queue import Queue, Empty
import time

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
                    self.processing = False
                    if response.startswith("Fout:"):
                        raise Exception(response)
                    return response
                except Empty:
                    if not self.processing:
                        if self.error:
                            raise Exception(self.error)
                        raise Exception("Agent stopte met verwerken zonder antwoord")
                    continue
            raise Exception("Timeout wachtend op antwoord (5 minuten)")
        except Exception as e:
            self.processing = False
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

def initialize_chat_session():
    """Initialize chat history in session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_manager" not in st.session_state:
        st.session_state.agent_manager = None

def render_chat_interface(config):
    """Render the chat interface."""
    initialize_chat_session()
    
    # Initialize agent if not already done
    if st.session_state.agent_manager is None:
        try:
            with st.spinner("Agent initialiseren..."):
                st.session_state.agent_manager = AgentManager(config)
                st.session_state.agent_manager.initialize()
        except Exception as e:
            st.error(f"Fout bij initialiseren FEWS agent: {str(e)}")
            return
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Stel een vraag over je FEWS configuratie..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Denken..."):
                try:
                    response = st.session_state.agent_manager.ask(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    error_msg = str(e)
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {error_msg}"})
    
    # Add session control buttons in sidebar
    with st.sidebar:
        st.markdown("### Chat Session")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        
        with col2:
            if st.button("Reset Agent", use_container_width=True):
                if st.session_state.agent_manager:
                    st.session_state.agent_manager.close()
                st.session_state.agent_manager = None
                st.session_state.messages = []
                st.rerun() 