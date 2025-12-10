"""
Streamlit Web Interface for URL Checker - Using Service Pattern
Real-time monitoring and configuration
"""

import streamlit as st
import time
import os
import logging
import warnings
from datetime import datetime
from pathlib import Path
import sys

# Suppress urllib3 connection pool warnings
warnings.filterwarnings('ignore', message='Connection pool is full')
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

# Suppress Tornado WebSocket warnings
logging.getLogger('tornado.access').setLevel(logging.ERROR)
logging.getLogger('tornado.application').setLevel(logging.ERROR)
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui import (
    render_config_sidebar,
    render_metrics,
    render_chart,
    render_logs,
    render_results_table
)
from src.services import (
    ConfigService,
    CheckerService,
    EmailService,
    StatsService
)


def initialize_services():
    """Initialize all services in session state"""
    if 'config_service' not in st.session_state:
        print("🔧 Initializing ConfigService...")
        st.session_state.config_service = ConfigService()
        print("✓ ConfigService initialized")
        
    if 'checker_service' not in st.session_state:
        print("🔧 Initializing CheckerService...")
        st.session_state.checker_service = CheckerService()
        print("✓ CheckerService initialized")
        
    if 'email_service' not in st.session_state:
        print("🔧 Initializing EmailService...")
        st.session_state.email_service = EmailService()
        print("✓ EmailService initialized")
        
    if 'stats_service' not in st.session_state:
        print("🔧 Initializing StatsService...")
        st.session_state.stats_service = StatsService()
        print("✓ StatsService initialized")
        
    if 'running' not in st.session_state:
        st.session_state.running = False
        
    if 'config' not in st.session_state:
        st.session_state.config = {}
    
    # Validate email configuration on startup
    if 'email_config_validated' not in st.session_state:
        print("\n" + "=" * 80)
        print("EMAIL CONFIGURATION VALIDATION")
        print("=" * 80)
        
        config_service = st.session_state.config_service
        try:
            config = config_service.load_config()
            email_config = config.get('email', {})
            brevo_config = config.get('brevo', {})
            
            recipient = email_config.get('recipient', '')
            api_key = brevo_config.get('api_key', os.getenv('BREVO_API_KEY', ''))
            
            if recipient:
                print(f"✓ Recipient email configured: {recipient}")
            else:
                print(f"⚠️  WARNING: No recipient email configured")
                print(f"   Configure in config.ini: [EMAIL] recipient = your@email.com")
            
            if api_key:
                print(f"✓ Brevo API key configured (length: {len(api_key)} chars)")
                
                # Test API key validity
                try:
                    import sib_api_v3_sdk
                    configuration = sib_api_v3_sdk.Configuration()
                    configuration.api_key['api-key'] = api_key
                    print(f"✓ Brevo client initialized")
                except Exception as e:
                    error_msg = str(e)
                    print(f"⚠️  Could not initialize Brevo client: {error_msg}")
            else:
                print(f"⚠️  WARNING: No Brevo API key configured")
                print(f"   Configure in config.ini: [BREVO] api_key = your-key")
                print(f"   Or set environment variable: BREVO_API_KEY")
            
            # Check if Brevo library is available
            try:
                import sib_api_v3_sdk
                print(f"✓ sib-api-v3-sdk library installed")
            except ImportError:
                print(f"⚠️  WARNING: sib-api-v3-sdk library NOT installed")
                print(f"   Install with: pip install sib-api-v3-sdk")
            
            # Final status
            if recipient and api_key:
                print(f"\n✅ Email functionality is ENABLED")
                print(f"   Emails will be sent to: {recipient}")
            else:
                print(f"\n❌ Email functionality is DISABLED")
                print(f"   Configure email settings to enable email reports")
                
        except Exception as e:
            print(f"❌ Error validating email configuration: {e}")
        
        print("=" * 80 + "\n")
        st.session_state.email_config_validated = True


def format_elapsed_time(seconds):
    """Format elapsed time in a readable format"""
    if seconds >= 3600:  # 1 hour or more
        hours = int(seconds / 3600)


def handle_start_check(config):
    """Handle start check button click"""
    stats_service = st.session_state.stats_service
    checker_service = st.session_state.checker_service
    
    # Reset statistics
    stats_service.reset()
    
    # Start checker
    st.session_state.running = True
    st.session_state.runtime_config = config
    checker_service.start_check(config)


def handle_stop_check():
    """Handle stop check button click"""
    checker_service = st.session_state.checker_service
    checker_service.stop_check()
    st.session_state.running = False


def send_email_if_needed():
    """Send email report if there are failures and email is configured"""
    stats_service = st.session_state.stats_service
    email_service = st.session_state.email_service
    config = st.session_state.get('runtime_config', {})
    
    stats = stats_service.get_stats()
    
    if stats['total_failed'] > 0:
        results = stats_service.get_results()
        success, message = email_service.send_failure_report(config, results)
        
        if success:
            st.info(f"📧 {message}")
        elif "No recipient" in message or "not configured" in message:
            st.info(f"ℹ️ {message}")
        else:
            st.warning(f"⚠️ {message}")


def process_checker_updates(progress_placeholder):
    """Process updates from checker service"""
    checker_service = st.session_state.checker_service
    stats_service = st.session_state.stats_service
    
    # Get updates from queue
    updates = checker_service.get_updates(max_updates=10)
    
    for update in updates:
        update_type = update['type']
        
        if update_type == 'page_update':
            stats_service.update_page(
                update['page'],
                update.get('total_pages', 0),
                update.get('total_urls', 0)
            )
            
        elif update_type == 'checking':
            stats_service.add_checking_log(
                update['url'],
                update['page'],
                update.get('attempt', 1),
                update['timestamp']
            )
            
        elif update_type == 'result':
            stats_service.add_result(
                update['url'],
                update['status'],
                update['page'],
                update['attempts'],
                update.get('response_time'),
                update['timestamp']
            )
            
        elif update_type == 'complete':
            st.session_state.running = False
            stats = stats_service.get_stats()
            
            stats_service.add_system_log(
                'complete',
                f"✅ Check completed! Total: {stats['total_checked']}, Failed: {stats['total_failed']}",
                datetime.now()
            )
            
            # Send email if needed
            send_email_if_needed()
            
            try:
                if stats['total_failed'] > 0:
                    st.warning(f"Found {stats['total_failed']} problematic URLs")
                else:
                    st.success("All URLs are working correctly!")
            except Exception:
                # Ignore WebSocket errors when connection is closed
                pass
                
        elif update_type == 'stopped':
            st.session_state.running = False
            stats_service.add_system_log(
                'stopped',
                "⏹️ Check stopped by user",
                datetime.now()
            )
            try:
                st.info("Check stopped")
            except Exception:
                # Ignore WebSocket errors when connection is closed
                pass
            
        elif update_type == 'error':
            st.session_state.running = False
            stats_service.add_system_log(
                'error',
                f"❌ Error: {update['error']}",
                datetime.now()
            )
            try:
                st.error(f"Error: {update['error']}")
            except Exception:
                # Ignore WebSocket errors when connection is closed
                pass
    
    # Update progress bar
    if updates:
        stats_service = st.session_state.stats_service
        stats = stats_service.get_stats()
        
        if stats['total_urls'] > 0:
            progress = stats_service.get_progress()
            progress_pct = int(progress * 100)
            elapsed_str = stats_service.get_elapsed_time()
            progress_placeholder.progress(
                min(progress, 1.0), 
                text=f"Progress: {progress_pct}% | Elapsed: {elapsed_str}"
            )


def main():
    st.set_page_config(
        page_title="URL Checker - Turing ES",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 URL Checker - Turing ES")
    st.markdown("### Real-time URL validation with Selenium")
    
    # Initialize services
    initialize_services()
    
    # Get services from session state
    stats_service = st.session_state.stats_service
    checker_service = st.session_state.checker_service
    
    # Render configuration sidebar
    config = render_config_sidebar()
    
    # Render metrics
    render_metrics(stats_service)
    
    # Control buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if st.button("▶️ Start Check", disabled=st.session_state.running, use_container_width=True):
            handle_start_check(config)
            st.rerun()
    
    with col2:
        if st.button("⏹️ Stop", disabled=not st.session_state.running, use_container_width=True):
            handle_stop_check()
    
    # Monitoring section (only when running or has data)
    stats = stats_service.get_stats()
    logs = stats_service.get_logs(1)
    
    if st.session_state.running or logs:
        st.divider()
        st.subheader("📊 Real-time Monitoring")
        
        # Create structure OUTSIDE the loop - single fixed container
        progress_placeholder = st.empty()
        
        # Single monitoring container that never changes position
        monitoring_container = st.container()
        
        # Initialize progress bar
        if stats['total_pages'] > 0:
            progress = stats_service.get_progress()
            progress_pct = int(progress * 100)
            elapsed_str = stats_service.get_elapsed_time()
            progress_placeholder.progress(progress, text=f"Progress: {progress_pct}% | Elapsed: {elapsed_str}")
        else:
            progress_placeholder.progress(0.0, text="Progress: 0% | Elapsed: 0s")
        
        # Process queue updates if running
        if st.session_state.running and checker_service.is_running():
            process_checker_updates(progress_placeholder)
        elif st.session_state.running and not checker_service.is_running():
            # Checker finished but still need to process final events in queue
            process_checker_updates(progress_placeholder)
        
        # Render everything inside the fixed monitoring container
        with monitoring_container:
            render_chart(stats_service)
            render_logs(stats_service)
        
        # Continue checking for updates if still running
        if st.session_state.running and checker_service.is_running():
            time.sleep(0.5)  # 500ms refresh rate
            st.rerun()
        elif st.session_state.running and not checker_service.is_running():
            # One more rerun to ensure final state is displayed
            time.sleep(0.5)
            st.rerun()
    
    # Results table
    render_results_table(stats_service)


if __name__ == "__main__":
    main()
