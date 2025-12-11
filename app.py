"""
URL Checker - Unified Application
Supports both GUI (Streamlit) and CLI modes
"""

import sys
import argparse
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Suppress warnings early (before any Streamlit imports)
import warnings
import logging
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.ERROR)


def is_streamlit_running():
    """Check if running in Streamlit context"""
    try:
        import streamlit as st
        # Try to access session_state - only works in Streamlit context
        _ = st.session_state
        return True
    except (ImportError, RuntimeError, AttributeError):
        return False


def run_cli():
    """Run in CLI mode"""
    import logging
    import warnings
    import urllib3
    from datetime import datetime
    from src.config_loader import ConfigLoader
    from src.services import CheckerService, StatsService, ConfigService, EmailService
    from src.report_generator import ReportGenerator
    
    def setup_logging(verbose: bool = False):
        """Configure logging system"""
        import os
        
        # Create logs directory
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Configure level and format
        level = logging.DEBUG if verbose else logging.WARNING  # Changed to WARNING to suppress info messages
        log_file = f"logs/url_checker_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Clear any existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )
        
        # Suppress all third-party library warnings
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
        logging.getLogger('streamlit').setLevel(logging.ERROR)
        logging.getLogger('tornado').setLevel(logging.ERROR)
        logging.getLogger('selenium').setLevel(logging.ERROR)
        logging.getLogger('webdriver_manager').setLevel(logging.ERROR)
    
    def print_banner():
        """Display initial banner"""
        print("\n" + "=" * 80)
        print(" " * 20 + "URL CHECKER - TURING ES")
        print(" " * 25 + "Version 1.0.0")
        print("=" * 80 + "\n")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='URL Checker - Turing URL Validator')
    parser.add_argument('--config', default='config.ini', help='Configuration file')
    parser.add_argument('--url-name', help='Name of the base URL from config (e.g., prod-publish, stage-author)')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--headless', action='store_true', help='Headless mode (no GUI)')
    parser.add_argument('--no-email', action='store_true', help='Do not send email')
    args = parser.parse_args()
    
    # Configure logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Additional suppression after logging setup
    logging.getLogger('streamlit.runtime.scriptrunner_utils.script_run_context').setLevel(logging.ERROR)
    
    # Banner
    print_banner()
    
    try:
        # Load configurations
        logger.info("Loading configurations...")
        config = ConfigLoader(args.config)
        
        # Get all base URLs from config
        base_urls = {}
        api_section = config.config['API']
        for key in api_section:
            if key.startswith('base_url.'):
                value = api_section[key]
                if ';' in value:
                    name, url = value.split(';', 1)
                    base_urls[name.strip()] = url.strip()
        
        # Select base URL
        if args.url_name:
            if args.url_name not in base_urls:
                print(f"\n❌ ERROR: URL name '{args.url_name}' not found in config")
                print(f"\nAvailable URL names:")
                for name in sorted(base_urls.keys()):
                    print(f"  - {name}: {base_urls[name]}")
                return 1
            base_url = base_urls[args.url_name]
            print(f"\n✓ Using URL: {args.url_name}")
            print(f"  {base_url}\n")
        elif len(base_urls) == 1:
            name = list(base_urls.keys())[0]
            base_url = base_urls[name]
            print(f"\n✓ Using URL: {name}")
            print(f"  {base_url}\n")
        else:
            print("\n" + "=" * 80)
            print("SELECT BASE URL")
            print("=" * 80)
            names = sorted(base_urls.keys())
            for i, name in enumerate(names, 1):
                print(f"{i}. {name}")
                print(f"   {base_urls[name]}")
            print("=" * 80)
            
            while True:
                try:
                    choice = input("\nEnter number or name: ").strip()
                    
                    if choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(names):
                            selected_name = names[idx]
                            base_url = base_urls[selected_name]
                            print(f"\n✓ Selected: {selected_name}")
                            print(f"  {base_url}\n")
                            break
                        else:
                            print(f"Invalid number. Please enter 1-{len(names)}")
                    elif choice in base_urls:
                        base_url = base_urls[choice]
                        print(f"\n✓ Selected: {choice}")
                        print(f"  {base_url}\n")
                        break
                    else:
                        print(f"Invalid input. Enter number (1-{len(names)}) or name")
                except KeyboardInterrupt:
                    print("\n\n❌ Operation cancelled by user")
                    return 1
        
        # Get configurations
        locale = config.get('API', 'locale', 'pt')
        email_recipient = config.get('EMAIL', 'recipient')
        brevo_api_key = config.get('BREVO', 'api_key')
        
        # Selenium configurations
        page_load_timeout = config.get_int('SELENIUM', 'page_load_timeout', 15)
        element_wait_timeout = config.get_int('SELENIUM', 'element_wait_timeout', 10)
        headless = args.headless or config.get_bool('SELENIUM', 'headless', False)
        
        # Retry configurations
        max_attempts = config.get_int('RETRY', 'max_attempts', 3)
        retry_delay = config.get_float('RETRY', 'retry_delay', 2)
        
        # Performance configurations
        page_delay = config.get_float('PERFORMANCE', 'page_delay', 0.5)
        url_check_delay = config.get_float('PERFORMANCE', 'url_check_delay', 0.3)
        disable_images = config.get_bool('PERFORMANCE', 'disable_images', True)
        parallel_browsers = config.get_int('PERFORMANCE', 'parallel_browsers', 1)
        
        # Error status codes
        error_codes_str = config.get('PERFORMANCE', 'error_status_codes', '404')
        error_status_codes = [int(code.strip()) for code in error_codes_str.split(',') if code.strip().isdigit()]
        if not error_status_codes:
            error_status_codes = [404]
        
        # Checkpoint configuration
        resume_from_checkpoint = config.get_bool('PERFORMANCE', 'resume_from_checkpoint', True)
        
        # Report configurations
        output_dir = config.get('REPORT', 'output_dir', 'reports')
        
        # Check email configuration
        send_email = not args.no_email
        if send_email:
            print("=" * 80)
            print("EMAIL CONFIGURATION")
            print("=" * 80)
            
            if email_recipient:
                print(f"✓ Recipient email configured: {email_recipient}")
                
                if brevo_api_key:
                    print(f"✓ Brevo API Key configured")
                    print(f"✅ Email will be sent if problematic URLs are found")
                    logger.info(f"Email enabled - will send to {email_recipient}")
                else:
                    print(f"⚠️  WARNING: Brevo API Key NOT configured")
                    print(f"   Emails will NOT be sent")
                    send_email = False
                    logger.warning("Email disabled - Brevo API key not configured")
            else:
                print(f"ℹ️  Email not configured. No email will be sent.")
                send_email = False
                logger.info("Email disabled - no recipient configured")
            
            print("=" * 80 + "\n")
        else:
            logger.info("Email disabled - --no-email flag used")
            print("\nℹ️  Email disabled via --no-email flag\n")
        
        # Initialize services
        logger.info("Initializing services...")
        logger.info(f"Error status codes configured: {error_status_codes}")
        logger.info(f"Resume from checkpoint: {resume_from_checkpoint}")
        print(f"⚙️  Error status codes: {', '.join(map(str, error_status_codes))}")
        print(f"♻️  Resume from checkpoint: {'Enabled' if resume_from_checkpoint else 'Disabled'}\n")
        
        config_service = ConfigService()
        checker_service = CheckerService()
        stats_service = StatsService()
        email_service = EmailService()
        
        # Prepare configuration
        checker_config = {
            'base_url': base_url,
            'locale': locale,
            'page_load_timeout': page_load_timeout,
            'element_wait_timeout': element_wait_timeout,
            'headless': headless,
            'max_attempts': max_attempts,
            'retry_delay': retry_delay,
            'page_delay': page_delay,
            'url_check_delay': url_check_delay,
            'disable_images': disable_images,
            'parallel_browsers': parallel_browsers,
            'error_status_codes': error_status_codes,
            'resume_from_checkpoint': resume_from_checkpoint
        }
        
        # Start checking in background
        logger.info("Starting URL verification in background...")
        checker_service.start_check(checker_config)
        
        # Monitor progress
        print("\n" + "=" * 80)
        print("CHECKING PROGRESS")
        print("=" * 80)
        
        import time
        last_checked = 0
        
        while checker_service.is_running():
            # Get updates from queue
            updates = checker_service.get_updates(max_updates=10)
            
            for update in updates:
                if update['type'] == 'page_update':
                    stats_service.update_page(
                        update['page'],
                        update.get('total_pages', 0),
                        update.get('total_urls', 0)
                    )
                elif update['type'] == 'result':
                    stats_service.add_result(
                        update['url'],
                        update['status'],
                        update['page'],
                        update['attempts'],
                        update.get('response_time'),
                        update['timestamp']
                    )
                elif update['type'] == 'complete':
                    break
            
            # Display progress
            stats = stats_service.get_stats()
            if stats['total_checked'] > last_checked:
                last_checked = stats['total_checked']
                progress_pct = int((stats['total_checked'] / stats['total_urls'] * 100)) if stats['total_urls'] > 0 else 0
                elapsed = stats_service.get_elapsed_time()
                eta = stats.get('estimated_time', 'calculating...')
                
                print(f"\r  Progress: {stats['total_checked']}/{stats['total_urls']} ({progress_pct}%) | "
                      f"Failed: {stats['total_failed']} | Elapsed: {elapsed} | ETA: {eta}      ", end='', flush=True)
            
            time.sleep(0.5)
        
        print("\n" + "=" * 80 + "\n")
        
        # Get final results
        stats = stats_service.get_stats()
        failed_urls = stats_service.get_results()
        
        # Generate reports
        logger.info("Generating reports...")
        report_gen = ReportGenerator(output_dir, error_status_codes=error_status_codes)
        txt_report, json_report = report_gen.generate(failed_urls)
        
        print(f"\n📄 Reports generated:")
        print(f"  - {txt_report}")
        print(f"  - {json_report}")
        
        # Send email if needed
        print("\n" + "=" * 80)
        print("EMAIL STATUS")
        print("=" * 80)
        
        if len(failed_urls) == 0:
            print("✅ No problematic URLs found. Email will not be sent.")
            logger.info("No failed URLs - email not needed")
        elif not send_email:
            print("ℹ️  Email not configured or disabled (--no-email flag)")
            logger.info("Email sending disabled or not configured")
        elif send_email and len(failed_urls) > 0:
            try:
                print(f"\n📧 Sending email report to: {email_recipient}")
                print(f"   Failed URLs to report: {len(failed_urls)}")
                logger.info(f"Attempting to send email to {email_recipient}")
                
                result = email_service.send_results_email(stats_service)
                
                if result.get('success'):
                    print(f"✅ Email successfully sent to: {email_recipient}")
                    logger.info(f"Email successfully sent to {email_recipient}")
                else:
                    print(f"⚠️  {result.get('message', 'Failed to send email')}")
                    logger.warning(f"Email not sent: {result.get('message')}")
                
            except ImportError as e:
                print(f"❌ Import Error: Missing required library - {e}")
                print(f"   Install with: pip install sib-api-v3-sdk")
                logger.error(f"Import error sending email: {e}")
            except Exception as e:
                print(f"❌ Error sending email: {e}")
                logger.error(f"Error sending email: {e}")
        
        print("=" * 80)
        
        # Final summary
        print("\n" + "=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"✓ Verification completed successfully!")
        print(f"  Total URLs checked: {stats['total_checked']}")
        print(f"  Problematic URLs: {stats['total_failed']}")
        print("=" * 80 + "\n")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"\n❌ ERROR: {e}")
        return 1
    except Exception as e:
        logger.exception("Error during execution")
        print(f"\n❌ ERROR: {e}")
        return 1


def run_gui():
    """Run in Streamlit GUI mode"""
    import streamlit as st
    import time
    import logging
    import warnings
    import os
    
    # Suppress Streamlit warnings
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    
    # Suppress other warnings
    warnings.filterwarnings('ignore', message='Connection pool is full')
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    logging.getLogger('tornado.access').setLevel(logging.ERROR)
    logging.getLogger('tornado.application').setLevel(logging.ERROR)
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    
    # Import Streamlit-dependent modules only in GUI mode
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
    # Check if running in Streamlit context
    if is_streamlit_running():
        # GUI mode
        run_gui()
    else:
        # CLI mode
        sys.exit(run_cli())
