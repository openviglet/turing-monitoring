"""CLI - Command Line Interface for URL Checker"""

import sys
import argparse
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
    level = logging.DEBUG if verbose else logging.INFO
    log_file = f"logs/url_checker_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    
    # Suppress warnings
    warnings.filterwarnings('ignore')
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def print_banner():
    """Display initial banner"""
    print("\n" + "=" * 80)
    print(" " * 20 + "URL CHECKER - TURING ES")
    print(" " * 25 + "Version 1.0.0")
    print("=" * 80 + "\n")


def main():
    """Main function"""
    # Parse arguments
    parser = argparse.ArgumentParser(description='URL Checker - Turing URL Validator')
    parser.add_argument('--config', default='config.ini', help='Configuration file')
    parser.add_argument('--url-name', help='Name of the base URL from config (e.g., prod-publish, stage-author)')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--headless', action='store_true', help='Headless mode (no GUI)')
    parser.add_argument('--no-email', action='store_true', help='Do not send email')
    parser.add_argument('--skip-driver-check', action='store_true', help='Skip ChromeDriver version check (use system driver)')
    args = parser.parse_args()
    
    # Configure logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Banner
    print_banner()
    
    try:
        # Load configurations using ConfigService (same as web interface)
        logger.info("Loading configurations...")
        config_service = ConfigService()
        default_config = config_service.get_default_config()
        
        # Get all base URLs from config
        base_urls = default_config['base_urls']
        
        # Select base URL
        if args.url_name:
            # Use specified URL name
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
            # Only one URL available
            name = list(base_urls.keys())[0]
            base_url = base_urls[name]
            print(f"\n✓ Using URL: {name}")
            print(f"  {base_url}\n")
        else:
            # Multiple URLs available - show menu
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
                    
                    # Try as number
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
                    # Try as name
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
        
        # Get configurations from ConfigService (centralized, same as web)
        email_recipient = default_config['email']['recipient']
        email_sender = default_config['email']['sender_email']
        email_sender_name = default_config['email']['sender_name']
        brevo_api_key = default_config['brevo']['api_key']
        
        # Override headless from args if provided
        headless = args.headless or default_config['headless']
        
        # Override skip_driver_version_check from args if provided
        skip_driver_check = args.skip_driver_check or default_config['skip_driver_version_check']
        
        # Report configurations
        config_loader = ConfigLoader(args.config)
        output_dir = config_loader.get('REPORT', 'output_dir', 'reports')
        max_urls_in_email = config_loader.get_int('REPORT', 'max_urls_in_email', 50)
        
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
                    print(f"   Configure in config.ini: [BREVO] api_key = your-key")
                    print(f"   Or set environment variable: BREVO_API_KEY")
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
        
        # Create checker
        logger.info("Initializing checker...")
        logger.info(f"Error status codes configured: {default_config['error_status_codes']}")
        logger.info(f"Resume from checkpoint: {default_config['resume_from_checkpoint']}")
        logger.info(f"Plugin: {default_config['plugin_name']}")
        print(f"⚙️  Error status codes: {', '.join(map(str, default_config['error_status_codes']))}")
        print(f"♻️  Resume from checkpoint: {'Enabled' if default_config['resume_from_checkpoint'] else 'Disabled'}")
        print(f"🔌 Plugin: {default_config['plugin_name']}\n")
        
        # Initialize services (same as Streamlit app)
        config_service = ConfigService()
        checker_service = CheckerService()
        stats_service = StatsService()
        email_service = EmailService()
        
        # Force complete reset (clear any checkpoint/previous data)
        stats_service.reset()
        logger.info(f"Stats reset - total_failed: {stats_service.get_stats()['total_failed']}")
        
        # Clear any existing checkpoint to start fresh (unless resuming)
        checkpoint_file = 'checkpoints/checker_progress.json'
        if not default_config['resume_from_checkpoint'] and os.path.exists(checkpoint_file):
            try:
                os.remove(checkpoint_file)
                print(f"✓ Cleared previous checkpoint\n")
                logger.info("Checkpoint file removed")
            except Exception as e:
                logger.warning(f"Could not remove checkpoint: {e}")
        
        # Prepare configuration for CheckerService (use default_config directly)
        checker_config = {
            'base_url': base_url,
            'locale': default_config['locale'],
            'page_load_timeout': default_config['page_load_timeout'],
            'element_wait_timeout': default_config['element_wait_timeout'],
            'headless': headless,
            'max_attempts': default_config['max_attempts'],
            'retry_delay': default_config['retry_delay'],
            'page_delay': default_config['page_delay'],
            'url_check_delay': default_config['url_check_delay'],
            'disable_images': default_config['disable_images'],
            'parallel_browsers': default_config['parallel_browsers'],
            'error_status_codes': default_config['error_status_codes'],
            'resume_from_checkpoint': default_config['resume_from_checkpoint'],
            'plugin_name': default_config['plugin_name'],
            'skip_driver_version_check': skip_driver_check
        }
        
        # Start checking in background (same as Streamlit)
        logger.info("Starting URL verification in background...")
        checker_service.start_check(checker_config)
        
        # Monitor progress
        print("\n" + "=" * 80)
        print("CHECKING PROGRESS")
        print("=" * 80)
        print("(Press Ctrl+C to stop)\n")
        
        import time
        last_display_time = time.time()
        has_displayed = False
        
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
                elif update['type'] == 'checking':
                    stats_service.add_checking_log(
                        update['url'],
                        update['page'],
                        update.get('attempt', 1),
                        update['timestamp']
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
            
            # Display progress (update every 0.3s or when data changes)
            current_time = time.time()
            stats = stats_service.get_stats()
            
            should_display = (
                (current_time - last_display_time >= 0.3) and 
                (stats['total_urls'] > 0 and stats['total_checked'] > 0)
            )
            
            if should_display or not has_displayed:
                progress_pct = int((stats['total_checked'] / stats['total_urls'] * 100)) if stats['total_urls'] > 0 else 0
                elapsed = stats_service.get_elapsed_time()
                eta = stats.get('estimated_time', 'calculating...')
                rps = stats_service.get_requests_per_second()
                
                # Build progress line
                progress_line = (
                    f"\r  Page {stats['current_page']}/{stats['total_pages']} | "
                    f"URLs: {stats['total_checked']}/{stats['total_urls']} ({progress_pct}%) | "
                    f"Failed: {stats['total_failed']} | "
                    f"Speed: {rps:.1f} req/s | "
                    f"Elapsed: {elapsed} | "
                    f"ETA: {eta}"
                )
                
                print(progress_line.ljust(120), end='', flush=True)
                
                last_display_time = current_time
                has_displayed = True
            
            time.sleep(0.5)
        
        print("\n" + "=" * 80 + "\n")
        
        # Get final results
        stats = stats_service.get_stats()
        failed_urls = stats_service.get_results()
        
        # Generate reports
        logger.info("Generating reports...")
        report_gen = ReportGenerator(output_dir, error_status_codes=default_config['error_status_codes'])
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
                
                # Use EmailService (same as Streamlit)
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
                import traceback
                logger.debug(traceback.format_exc())
            except Exception as e:
                print(f"❌ Error sending email: {e}")
                print(f"   Error type: {type(e).__name__}")
                logger.error(f"Error sending email: {e}")
                import traceback
                error_trace = traceback.format_exc()
                logger.debug(f"Full error traceback:\n{error_trace}")
                print(f"\n🔍 DEBUG - Full error details logged to log file")
        
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


if __name__ == "__main__":
    sys.exit(main())
