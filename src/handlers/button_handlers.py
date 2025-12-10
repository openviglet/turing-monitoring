"""
Button Handlers
Handles all button click actions in the UI
"""

import os
import time
import streamlit as st
from ..utils.constants import (
    CHECKPOINT_FILE,
    CHECKPOINT_DELETE_ATTEMPTS,
    CHECKPOINT_DELETE_RETRY_DELAY
)


class ButtonHandlers:
    """Handles button click events"""
    
    @staticmethod
    def handle_start(config):
        """Handle start button click"""
        stats_service = st.session_state.stats_service
        checker_service = st.session_state.checker_service
        
        checkpoint_exists = os.path.exists(CHECKPOINT_FILE)
        
        if checkpoint_exists:
            print("💾 Resuming from checkpoint...")
            stats_service.load_from_checkpoint()
        else:
            print("🆕 Starting fresh - resetting statistics...")
            stats_service.reset()
        
        # Start checker
        st.session_state.running = True
        st.session_state.paused = False
        st.session_state.runtime_config = config
        checker_service.start_check(config)
    
    @staticmethod
    def handle_stop():
        """Handle stop button click - stops and clears checkpoint"""
        checker_service = st.session_state.checker_service
        stats_service = st.session_state.stats_service
        
        print("🛑 Stop requested - cleaning up...")
        
        # Stop the checker thread
        checker_service.stop_check()
        
        # Reset UI state
        st.session_state.running = False
        st.session_state.paused = False
        
        # Wait to ensure thread is stopped
        time.sleep(1.0)
        
        # Clear statistics
        stats_service.reset()
        
        # Clear checkpoint with retry
        ButtonHandlers._clear_checkpoint()
        
        print("✓ Stop completed - ready for new run")
    
    @staticmethod
    def handle_pause():
        """Handle pause button click - pauses but keeps checkpoint"""
        checker_service = st.session_state.checker_service
        
        checker_service.pause_check()
        st.session_state.running = False
        st.session_state.paused = True
        print("⏸️  Paused - checker waiting for resume")
    
    @staticmethod
    def handle_resume(config):
        """Handle resume button click - continues from checkpoint"""
        stats_service = st.session_state.stats_service
        checker_service = st.session_state.checker_service
        
        print(f"🔄 Resume requested - running={st.session_state.running}, paused={st.session_state.paused}")
        
        # Check if thread is already running (after pause)
        if checker_service.is_running():
            print("✓ Checker thread already running - resuming from pause")
            checker_service.resume_check()
            st.session_state.running = True
            st.session_state.paused = False
            return
        
        # If thread is not running, start fresh from checkpoint
        print("⚠️  No running thread - starting new one from checkpoint")
        
        checkpoint_exists = os.path.exists(CHECKPOINT_FILE)
        if checkpoint_exists:
            print("💾 Loading from checkpoint...")
            stats_service.load_from_checkpoint()
        else:
            print("⚠️  No checkpoint found, starting fresh")
        
        # Start checker
        st.session_state.running = True
        st.session_state.paused = False
        st.session_state.runtime_config = config
        checker_service.start_check(config)
    
    @staticmethod
    def _clear_checkpoint():
        """Clear checkpoint file with retry logic"""
        for attempt in range(CHECKPOINT_DELETE_ATTEMPTS):
            if os.path.exists(CHECKPOINT_FILE):
                try:
                    os.remove(CHECKPOINT_FILE)
                    print(f"🗑️  Checkpoint cleared (attempt {attempt + 1})")
                    break
                except Exception as e:
                    print(f"⚠️  Failed to delete checkpoint (attempt {attempt + 1}): {e}")
                    time.sleep(CHECKPOINT_DELETE_RETRY_DELAY)
