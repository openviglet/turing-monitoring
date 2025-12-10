"""
Process Manager
Manages background process updates and queue processing
"""

import streamlit as st
from datetime import datetime


class ProcessManager:
    """Manages process updates from checker service"""
    
    @staticmethod
    def process_updates(progress_placeholder):
        """Process updates from checker service queue"""
        checker_service = st.session_state.checker_service
        stats_service = st.session_state.stats_service
        
        # Get updates from queue
        updates = checker_service.get_updates(max_updates=10)
        
        for update in updates:
            ProcessManager._handle_update(update, stats_service)
        
        # Update progress bar if there were updates
        if updates:
            ProcessManager._update_progress(progress_placeholder, stats_service)
    
    @staticmethod
    def _handle_update(update: dict, stats_service):
        """Handle a single update from the queue"""
        update_type = update['type']
        
        if update_type == 'page_update':
            ProcessManager._handle_page_update(update, stats_service)
        elif update_type == 'checking':
            ProcessManager._handle_checking_update(update, stats_service)
        elif update_type == 'result':
            ProcessManager._handle_result_update(update, stats_service)
        elif update_type == 'complete':
            ProcessManager._handle_complete_update(stats_service)
        elif update_type == 'stopped':
            ProcessManager._handle_stopped_update(stats_service)
        elif update_type == 'error':
            ProcessManager._handle_error_update(update, stats_service)
    
    @staticmethod
    def _handle_page_update(update: dict, stats_service):
        """Handle page update"""
        stats_service.update_page(
            update['page'],
            update.get('total_pages', 0),
            update.get('total_urls', 0)
        )
    
    @staticmethod
    def _handle_checking_update(update: dict, stats_service):
        """Handle checking status update"""
        stats_service.add_checking_log(
            update['url'],
            update['page'],
            update.get('attempt', 1),
            update['timestamp']
        )
    
    @staticmethod
    def _handle_result_update(update: dict, stats_service):
        """Handle result update"""
        stats_service.add_result(
            update['url'],
            update['status'],
            update['page'],
            update['attempts'],
            update.get('response_time'),
            update['timestamp']
        )
    
    @staticmethod
    def _handle_complete_update(stats_service):
        """Handle completion update"""
        st.session_state.running = False
        stats = stats_service.get_stats()
        
        stats_service.add_system_log(
            'complete',
            f"✅ Check completed! Total: {stats['total_checked']}, Failed: {stats['total_failed']}",
            datetime.now()
        )
        
        # Send email if needed
        ProcessManager._send_email_if_needed()
        
        try:
            if stats['total_failed'] > 0:
                st.warning(f"Found {stats['total_failed']} problematic URLs")
            else:
                st.success("All URLs are working correctly!")
        except Exception:
            pass  # Ignore WebSocket errors
    
    @staticmethod
    def _handle_stopped_update(stats_service):
        """Handle stopped update"""
        st.session_state.running = False
        stats_service.add_system_log(
            'stopped',
            "⏹️ Check stopped by user",
            datetime.now()
        )
        try:
            st.info("Check stopped")
        except Exception:
            pass  # Ignore WebSocket errors
    
    @staticmethod
    def _handle_error_update(update: dict, stats_service):
        """Handle error update"""
        st.session_state.running = False
        stats_service.add_system_log(
            'error',
            f"❌ Error: {update['error']}",
            datetime.now()
        )
        try:
            st.error(f"Error: {update['error']}")
        except Exception:
            pass  # Ignore WebSocket errors
    
    @staticmethod
    def _update_progress(progress_placeholder, stats_service):
        """Update progress bar"""
        stats = stats_service.get_stats()
        
        if stats['total_urls'] > 0:
            progress = stats_service.get_progress()
            progress_pct = int(progress * 100)
            elapsed_str = stats_service.get_elapsed_time()
            progress_placeholder.progress(
                progress,
                text=f"Progress: {progress_pct}% | Elapsed: {elapsed_str}"
            )
    
    @staticmethod
    def _send_email_if_needed():
        """Send email notification if configured"""
        try:
            config_service = st.session_state.config_service
            email_service = st.session_state.email_service
            stats_service = st.session_state.stats_service
            
            config = config_service.load_config()
            email_config = config.get('email', {})
            
            # Check if email is enabled
            if not email_config.get('enabled', True):
                return
            
            # Check if should send email
            send_condition = email_config.get('send_condition', 'always')
            stats = stats_service.get_stats()
            
            should_send = False
            if send_condition == 'always':
                should_send = True
            elif send_condition == 'on_failure' and stats['total_failed'] > 0:
                should_send = True
            elif send_condition == 'on_success' and stats['total_failed'] == 0:
                should_send = True
            
            if should_send:
                result = email_service.send_results_email(stats_service)
                ProcessManager._display_email_status(result)
        except Exception as e:
            print(f"Error sending email: {e}")
    
    @staticmethod
    def _display_email_status(result: dict):
        """Display email send status"""
        if not result:
            return
        
        message = result.get('message', '')
        
        try:
            if result.get('success'):
                st.success(f"📧 {message}")
            elif "Email sent" in message:
                st.info(f"📧 {message}")
            elif "No recipient" in message or "not configured" in message:
                st.info(f"ℹ️ {message}")
            else:
                st.warning(f"⚠️ {message}")
        except Exception:
            pass  # Ignore WebSocket errors
