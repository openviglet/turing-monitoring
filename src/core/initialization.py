"""
Service Initialization
Handles initialization and configuration of all services
"""

import streamlit as st
import os
from ..services import ConfigService, CheckerService, EmailService, StatsService
from ..utils.constants import CHECKPOINT_FILE


class ServiceInitializer:
    """Initializes and configures all application services"""
    
    @staticmethod
    def initialize_all():
        """Initialize all services in session state"""
        ServiceInitializer._init_config_service()
        ServiceInitializer._init_checker_service()
        ServiceInitializer._init_email_service()
        ServiceInitializer._init_stats_service()
        ServiceInitializer._handle_background_process()
        ServiceInitializer._validate_email_config()
    
    @staticmethod
    def _init_config_service():
        """Initialize configuration service"""
        if 'config_service' not in st.session_state:
            print("🔧 Initializing ConfigService...")
            st.session_state.config_service = ConfigService()
            print("✓ ConfigService initialized")
    
    @staticmethod
    def _init_checker_service():
        """Initialize checker service"""
        if 'checker_service' not in st.session_state:
            print("🔧 Initializing CheckerService...")
            st.session_state.checker_service = CheckerService()
            print("✓ CheckerService initialized")
    
    @staticmethod
    def _init_email_service():
        """Initialize email service"""
        if 'email_service' not in st.session_state:
            print("🔧 Initializing EmailService...")
            st.session_state.email_service = EmailService()
            print("✓ EmailService initialized")
    
    @staticmethod
    def _init_stats_service():
        """Initialize statistics service"""
        if 'stats_service' not in st.session_state:
            print("🔧 Initializing StatsService...")
            st.session_state.stats_service = StatsService()
            print("✓ StatsService initialized")
    
    @staticmethod
    def _handle_background_process():
        """Check for and handle background processes"""
        if st.session_state.get('running', False):
            return  # Already initialized
        
        checker_service = st.session_state.checker_service
        stats_service = st.session_state.stats_service
        
        is_thread_running = checker_service.is_running()
        checkpoint_exists = os.path.exists(CHECKPOINT_FILE)
        
        print(f"Thread running: {is_thread_running}")
        print(f"Checkpoint exists: {checkpoint_exists}")
        
        if is_thread_running:
            print("🔄 Detected background process running, reconnecting...")
            st.session_state.running = True
            
            # Only show reconnection message if not already paused
            if not st.session_state.get('paused', False):
                st.session_state.reconnected = True
            st.session_state.force_rerun = True
            
            # Try to load checkpoint data
            if stats_service.load_from_checkpoint():
                print("✓ Loaded checkpoint data into statistics")
            else:
                print("⚠️  Could not load checkpoint data, starting with empty stats")
        elif checkpoint_exists:
            print("💾 Checkpoint found but no active process")
            print("   Process will resume from checkpoint when started")
    
    @staticmethod
    def _validate_email_config():
        """Validate email configuration on startup"""
        if 'email_config_validated' in st.session_state:
            return
        
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
            
            # Validate recipient
            if recipient:
                print(f"✓ Recipient email configured: {recipient}")
            else:
                print("⚠️  WARNING: No recipient email configured")
                print("   Configure in config.ini: [EMAIL] recipient = your@email.com")
            
            # Validate API key
            if api_key:
                print(f"✓ Brevo API key configured (length: {len(api_key)} chars)")
                ServiceInitializer._test_brevo_client(api_key)
            else:
                print("⚠️  WARNING: No Brevo API key configured")
                print("   Configure in config.ini: [BREVO] api_key = your-key")
                print("   Or set environment variable: BREVO_API_KEY")
            
            # Check library availability
            ServiceInitializer._check_brevo_library()
            
            # Final status
            if recipient and api_key:
                print("\n✅ Email functionality is ENABLED")
                print(f"   Emails will be sent to: {recipient}")
            else:
                print("\n❌ Email functionality is DISABLED")
                print("   Configure email settings to enable email reports")
                
        except Exception as e:
            print(f"❌ Error validating email configuration: {e}")
        
        print("=" * 80 + "\n")
        st.session_state.email_config_validated = True
    
    @staticmethod
    def _test_brevo_client(api_key: str):
        """Test Brevo client initialization"""
        try:
            import sib_api_v3_sdk
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = api_key
            print("✓ Brevo client initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize Brevo client: {str(e)}")
    
    @staticmethod
    def _check_brevo_library():
        """Check if Brevo library is installed"""
        try:
            import sib_api_v3_sdk
            print("✓ sib-api-v3-sdk library installed")
        except ImportError:
            print("⚠️  WARNING: sib-api-v3-sdk library NOT installed")
            print("   Install with: pip install sib-api-v3-sdk")
