"""
Streamlit Web Interface for URL Checker
"""

import streamlit as st
import time
import logging
import warnings
from pathlib import Path
import sys

# Suppress warnings
warnings.filterwarnings('ignore')
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('tornado.access').setLevel(logging.ERROR)
logging.getLogger('tornado.application').setLevel(logging.ERROR)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui import (
    render_config_sidebar,
    render_metrics,
    render_chart,
    render_logs,
    render_results_table
)
from src.core import StateManager, ServiceInitializer, ProcessManager
from src.handlers import ButtonHandlers
from src.utils.constants import (
    START_DELAY,
    RESUME_DELAY,
    PAUSE_DELAY,
    STOP_DELAY,
    DEFAULT_REFRESH_RATE,
    PROCESSING_MESSAGE,
    DEFAULT_LOG_COUNT
)


def handle_reconnection_message():
    """Display reconnection message if applicable"""
    if not st.session_state.get('reconnected', False):
        return
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success("🔄 Reconnected to running process! The check is still in progress.")
    with col2:
        stats = st.session_state.stats_service.get_stats()
        if stats['current_page'] > 0:
            st.info(f"💾 Page {stats['current_page']} | {stats['total_checked']} checked")
    st.session_state.reconnected = False


def render_control_buttons(config):
    """Render Start/Resume/Pause/Stop buttons"""
    is_running = StateManager.is_running()
    is_paused = StateManager.is_paused()
    is_processing = StateManager.is_processing()
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    
    with col1:
        if is_paused:
            if st.button("▶️ Resume", disabled=is_processing, use_container_width=True):
                StateManager.set_processing(True, 'resume')
                st.rerun()
        else:
            if st.button("▶️ Start", disabled=is_running or is_processing, use_container_width=True):
                StateManager.set_processing(True, 'start')
                st.rerun()
    
    with col2:
        if st.button("⏸️ Pause", disabled=not is_running or is_paused or is_processing, use_container_width=True):
            StateManager.set_processing(True, 'pause')
            st.rerun()
    
    with col3:
        if st.button("⏹️ Stop", disabled=(not is_running and not is_paused) or is_processing, use_container_width=True):
            StateManager.set_processing(True, 'stop')
            st.rerun()


def handle_processing_action(config):
    """Handle pending processing actions"""
    if not StateManager.is_processing():
        return False
    
    action = StateManager.get_processing_action()
    if not action:
        return False
    
    StateManager.clear_processing_action()
    
    if action == 'start':
        ButtonHandlers.handle_start(config)
        time.sleep(START_DELAY)
    elif action == 'resume':
        ButtonHandlers.handle_resume(config)
        time.sleep(RESUME_DELAY)
    elif action == 'pause':
        ButtonHandlers.handle_pause()
        time.sleep(PAUSE_DELAY)
    elif action == 'stop':
        ButtonHandlers.handle_stop()
        time.sleep(STOP_DELAY)
    
    StateManager.set_processing(False)
    st.rerun()
    st.stop()


def render_monitoring_section(stats_service, checker_service):
    """Render real-time monitoring section"""
    stats = stats_service.get_stats()
    logs = stats_service.get_logs(DEFAULT_LOG_COUNT)
    
    if not (StateManager.is_running() or logs):
        return
    
    st.divider()
    st.subheader("📊 Real-time Monitoring")
    
    # Create fixed containers
    progress_placeholder = st.empty()
    monitoring_container = st.container()
    
    # Initialize progress bar
    if stats['total_pages'] > 0:
        progress = stats_service.get_progress()
        progress_pct = int(progress * 100)
        elapsed_str = stats_service.get_elapsed_time()
        progress_placeholder.progress(progress, text=f"Progress: {progress_pct}% | Elapsed: {elapsed_str}")
    else:
        progress_placeholder.progress(0.0, text="Progress: 0% | Elapsed: 0s")
    
    # Process queue updates if running and not paused
    is_running = StateManager.is_running()
    is_paused = StateManager.is_paused()
    thread_alive = checker_service.is_running()
    
    if is_running and not is_paused and thread_alive:
        ProcessManager.process_updates(progress_placeholder)
    elif is_running and not is_paused and not thread_alive:
        ProcessManager.process_updates(progress_placeholder)
    elif not is_running and not is_paused and thread_alive:
        # Reconnect after browser refresh
        StateManager.set_running(True)
        st.info("🔄 Background process detected, reconnecting...")
        st.rerun()
    
    # Render monitoring components
    with monitoring_container:
        render_chart(stats_service)
        render_logs(stats_service)
    
    # Continue checking for updates if still running
    if is_running and not is_paused and thread_alive:
        time.sleep(DEFAULT_REFRESH_RATE)
        st.rerun()
    elif is_running and not is_paused and not thread_alive:
        time.sleep(DEFAULT_REFRESH_RATE)
        st.rerun()


def main():
    st.set_page_config(
        page_title="URL Checker - Turing ES",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 URL Checker - Turing ES")
    st.markdown("### Real-time URL validation with Selenium")
    
    # Initialize state and services
    StateManager.initialize_state()
    ServiceInitializer.initialize_all()
    
    # Force rerun if reconnected
    if st.session_state.get('force_rerun', False):
        st.session_state.force_rerun = False
        print("🔄 Forcing UI refresh after reconnection...")
        st.rerun()
    
    # Show reconnection message
    handle_reconnection_message()
    
    # Get services
    stats_service = st.session_state.stats_service
    checker_service = st.session_state.checker_service
    
    # Render UI components
    config = render_config_sidebar()
    render_metrics(stats_service)
    
    # Show processing notification
    if StateManager.is_processing():
        st.info(PROCESSING_MESSAGE)
    
    # Control buttons
    render_control_buttons(config)
    
    # Handle processing actions
    handle_processing_action(config)
    
    # Monitoring section
    render_monitoring_section(stats_service, checker_service)
    
    # Results table
    render_results_table(stats_service)


if __name__ == "__main__":
    main()
