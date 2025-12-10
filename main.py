"""Main - Application entry point"""

import sys
import argparse
import logging
from datetime import datetime
from src.config_loader import ConfigLoader
from src.checker import URLChecker
from src.report_generator import ReportGenerator
from src.email_sender import EmailSender


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
        ]
    )


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
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--headless', action='store_true', help='Headless mode (no GUI)')
    parser.add_argument('--no-email', action='store_true', help='Do not send email')
    args = parser.parse_args()
    
    # Configure logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Banner
    print_banner()
    
    try:
        # Load configurations
        logger.info("Loading configurations...")
        config = ConfigLoader(args.config)
        
        # Get configurations
        base_url = config.get('API', 'base_url')
        locale = config.get('API', 'locale', 'pt')
        email_recipient = config.get('EMAIL', 'recipient')
        email_sender = config.get('EMAIL', 'sender_email')
        email_sender_name = config.get('EMAIL', 'sender_name')
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
        
        # Error status codes configuration
        error_codes_str = config.get('PERFORMANCE', 'error_status_codes', '404')
        error_status_codes = [int(code.strip()) for code in error_codes_str.split(',') if code.strip().isdigit()]
        if not error_status_codes:
            error_status_codes = [404]  # Default to 404 if invalid
        
        # Checkpoint configuration
        resume_from_checkpoint = config.get_bool('PERFORMANCE', 'resume_from_checkpoint', True)
        
        # Report configurations
        output_dir = config.get('REPORT', 'output_dir', 'reports')
        max_urls_in_email = config.get_int('REPORT', 'max_urls_in_email', 50)
        
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
        logger.info(f"Error status codes configured: {error_status_codes}")
        logger.info(f"Resume from checkpoint: {resume_from_checkpoint}")
        print(f"⚙️  Error status codes: {', '.join(map(str, error_status_codes))}")
        print(f"♻️  Resume from checkpoint: {'Enabled' if resume_from_checkpoint else 'Disabled'}\n")
        checker = URLChecker(
            base_url=base_url,
            locale=locale,
            page_load_timeout=page_load_timeout,
            element_wait_timeout=element_wait_timeout,
            headless=headless,
            max_attempts=max_attempts,
            retry_delay=retry_delay,
            page_delay=page_delay,
            url_check_delay=url_check_delay,
            disable_images=disable_images,
            parallel_browsers=parallel_browsers,
            error_status_codes=error_status_codes,
            resume_from_checkpoint=resume_from_checkpoint
        )
        
        # Execute verification
        logger.info("Starting URL verification...")
        failed_urls = checker.run()
        
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
                # Detailed debug logging
                print(f"\n🔍 DEBUG - Email Configuration:")
                print(f"   Recipient: {email_recipient}")
                print(f"   Sender: {email_sender}")
                print(f"   Sender Name: {email_sender_name}")
                print(f"   Brevo API Key: {'*' * 20}{brevo_api_key[-10:] if brevo_api_key and len(brevo_api_key) > 10 else 'NOT_SET'}")
                print(f"   Failed URLs count: {len(failed_urls)}")
                print(f"   TXT Report: {txt_report}")
                print(f"   JSON Report: {json_report}")
                print(f"   Max URLs in email: {max_urls_in_email}")
                
                logger.debug(f"Email config - Recipient: {email_recipient}, Sender: {email_sender}")
                logger.debug(f"Brevo API key present: {bool(brevo_api_key)}, length: {len(brevo_api_key) if brevo_api_key else 0}")
                logger.debug(f"Failed URLs: {len(failed_urls)}, Reports: {txt_report}, {json_report}")
                
                print(f"\n📧 Sending email report to: {email_recipient}")
                print(f"   Failed URLs to report: {len(failed_urls)}")
                logger.info(f"Attempting to send email to {email_recipient}")
                
                # Create EmailSender instance
                print(f"   🔧 Creating EmailSender instance...")
                logger.debug("Creating EmailSender instance")
                email = EmailSender(
                    api_key=brevo_api_key,
                    sender_email=email_sender,
                    sender_name=email_sender_name,
                    max_urls_in_email=max_urls_in_email
                )
                logger.debug("EmailSender instance created successfully")
                
                # Send report
                print(f"   📤 Calling send_report method...")
                logger.debug("Calling EmailSender.send_report()")
                email.send_report(email_recipient, failed_urls, txt_report, json_report)
                logger.debug("send_report() completed without exceptions")
                
                print(f"✅ Email successfully sent to: {email_recipient}")
                logger.info(f"Email successfully sent to {email_recipient}")
                
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
        print(f"  Total URLs checked: {checker.total_urls_checked}")
        print(f"  Problematic URLs: {len(failed_urls)}")
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
