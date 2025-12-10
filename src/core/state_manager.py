"""
State Manager
Centralized management of Streamlit session state
"""

import streamlit as st
import os
from ..utils.constants import CHECKPOINT_FILE


class StateManager:
    """Manages Streamlit session state"""
    
    @staticmethod
    def initialize_state():
        """Initialize all session state variables"""
        StateManager._init_flags()
        StateManager._init_processing_state()
        StateManager._init_config()
    
    @staticmethod
    def _init_flags():
        """Initialize control flags"""
        if 'running' not in st.session_state:
            st.session_state.running = False
        
        if 'paused' not in st.session_state:
            checkpoint_exists = os.path.exists(CHECKPOINT_FILE)
            st.session_state.paused = checkpoint_exists
            if checkpoint_exists:
                print("💾 Checkpoint detected - use Resume to continue")
    
    @staticmethod
    def _init_processing_state():
        """Initialize processing state"""
        if 'processing' not in st.session_state:
            st.session_state.processing = False
        
        if 'processing_action' not in st.session_state:
            st.session_state.processing_action = None
    
    @staticmethod
    def _init_config():
        """Initialize configuration"""
        if 'config' not in st.session_state:
            st.session_state.config = {}
    
    @staticmethod
    def set_running(value: bool):
        """Set running state"""
        st.session_state.running = value
    
    @staticmethod
    def set_paused(value: bool):
        """Set paused state"""
        st.session_state.paused = value
    
    @staticmethod
    def set_processing(value: bool, action: str = None):
        """Set processing state and action"""
        st.session_state.processing = value
        st.session_state.processing_action = action
    
    @staticmethod
    def is_running() -> bool:
        """Check if running"""
        return st.session_state.get('running', False)
    
    @staticmethod
    def is_paused() -> bool:
        """Check if paused"""
        return st.session_state.get('paused', False)
    
    @staticmethod
    def is_processing() -> bool:
        """Check if processing"""
        return st.session_state.get('processing', False)
    
    @staticmethod
    def get_processing_action() -> str:
        """Get current processing action"""
        return st.session_state.get('processing_action')
    
    @staticmethod
    def clear_processing_action():
        """Clear processing action"""
        st.session_state.processing_action = None
