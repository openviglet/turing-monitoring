"""
Email Service - Handles email sending operations
"""

import os
from datetime import datetime
from ..email_sender import EmailSender


class EmailService:
    """Service for sending email reports"""
    
    def __init__(self):
        self.email_sender = None
    
    def send_failure_report(self, config, failed_results):
        """
        Send email report for failed URLs
        
        Args:
            config: Configuration dictionary with email settings
            failed_results: List of failed URL results
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not failed_results:
            return False, "No failed URLs to report"
        
        # Get email configuration
        email_config = config.get('email', {})
        brevo_config = config.get('brevo', {})
        
        recipient = email_config.get('recipient', '')
        
        if not recipient:
            return False, "No recipient email configured"
        
        sender_email = email_config.get('sender_email', 'noreply@example.com')
        sender_name = email_config.get('sender_name', 'URL Checker - Turing')
        api_key = brevo_config.get('api_key', os.getenv('BREVO_API_KEY', ''))
        
        print(f"[EmailService] Checking configuration:")
        print(f"  - Recipient: {recipient}")
        print(f"  - Sender: {sender_email}")
        print(f"  - API Key: {'Yes' if api_key else 'No'}")
        
        if not api_key:
            print(f"[EmailService] ERROR: Brevo API key not configured")
            return False, "Brevo API key not configured"
        
        try:
            # Filter failed URLs (status != 200) and normalize format
            failed_urls = []
            for result in failed_results:
                status = result.get('status') or result.get('status_code')
                if status and status != 200:
                    # Normalize the format to match what EmailSender expects
                    normalized = {
                        'url': result.get('url', 'N/A'),
                        'status_code': status,  # EmailSender expects 'status_code'
                        'page': result.get('page', 'N/A'),
                        'attempts': result.get('attempts', 1)
                    }
                    failed_urls.append(normalized)
            
            print(f"[EmailService] Filtered {len(failed_urls)} failed URLs from {len(failed_results)} results")
            
            if not failed_urls:
                print(f"[EmailService] ERROR: No failed URLs found in results")
                return False, "No failed URLs found in results"
            
            # Initialize email sender
            print(f"[EmailService] Initializing EmailSender...")
            self.email_sender = EmailSender(
                api_key=api_key,
                sender_email=sender_email,
                sender_name=sender_name,
                max_urls_in_email=50
            )
            print(f"[EmailService] EmailSender initialized successfully")
            
            # Generate temporary report paths
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_report = f"temp_report_{timestamp}.txt"
            json_report = f"temp_report_{timestamp}.json"
            
            print(f"[EmailService] Generated report filenames:")
            print(f"  - TXT: {txt_report}")
            print(f"  - JSON: {json_report}")
            
            # Create temporary report files
            print(f"[EmailService] Creating temporary report files...")
            self._create_report_files(failed_urls, txt_report, json_report)
            print(f"[EmailService] ✓ Report files created")
            
            # Send email
            print(f"[EmailService] Calling email_sender.send_report()...")
            self.email_sender.send_report(recipient, failed_urls, txt_report, json_report)
            
            # Clean up temporary files
            try:
                os.remove(txt_report)
                os.remove(json_report)
                print(f"[EmailService] ✓ Temporary files cleaned up")
            except:
                pass
            
            print(f"[EmailService] ✓ Email sent successfully to {recipient}")
            return True, f"Report sent to {recipient}"
            
        except Exception as e:
            print(f"[EmailService] ❌ Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Error sending email: {str(e)}"
    
    def _create_report_files(self, failed_urls, txt_path, json_path):
        """Create temporary report files"""
        import json
        
        # Create TXT report
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("URL VALIDATION REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total problematic URLs: {len(failed_urls)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, item in enumerate(failed_urls, 1):
                f.write(f"{i}. URL: {item.get('url', 'N/A')}\n")
                f.write(f"   Status Code: {item.get('status', 'N/A')}\n")
                f.write(f"   Page: {item.get('page', 'N/A')}\n")
                f.write(f"   Attempts: {item.get('attempts', 'N/A')}\n")
                f.write("-" * 80 + "\n")
        
        # Create JSON report
        with open(json_path, 'w', encoding='utf-8') as f:
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'total_failed': len(failed_urls),
                'failed_urls': failed_urls
            }
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    
    def is_email_configured(self, config):
        """Check if email is properly configured"""
        email_config = config.get('email', {})
        brevo_config = config.get('brevo', {})
        
        recipient = email_config.get('recipient', '')
        api_key = brevo_config.get('api_key', os.getenv('BREVO_API_KEY', ''))
        
        return bool(recipient and api_key)
    
    def send_results_email(self, stats_service):
        """
        Send email with results using stats service
        
        Args:
            stats_service: StatsService instance with results
            
        Returns:
            dict: Result with 'success' and 'message' keys
        """
        try:
            # Get failed URLs from stats
            stats = stats_service.get_stats()
            
            if stats['total_failed'] == 0:
                return {'success': False, 'message': 'No failed URLs to report'}
            
            # Get configuration
            from ..services import ConfigService
            config_service = ConfigService()
            config = config_service.load_config()
            
            # Get failed results
            failed_results = stats.get('failed_results', [])
            
            # Send report
            success, message = self.send_failure_report(config, failed_results)
            
            return {'success': success, 'message': message}
            
        except Exception as e:
            return {'success': False, 'message': f'Error preparing email: {str(e)}'}
