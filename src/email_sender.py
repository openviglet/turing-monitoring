"""
Email Sender - Sends reports via Brevo (Sendinblue)
"""

import os
import logging
import base64
from typing import List, Dict
from datetime import datetime

try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False


class EmailSender:
    """Email sender via Brevo (Sendinblue)"""
    
    def __init__(
        self,
        api_key: str,
        sender_email: str = "noreply@example.com",
        sender_name: str = "URL Checker - Turing",
        max_urls_in_email: int = 50
    ):
        """
        Initialize email sender
        
        Args:
            api_key: Brevo API key
            sender_email: Sender email address
            sender_name: Sender name
            max_urls_in_email: Maximum URLs to include in email body
        """
        if not BREVO_AVAILABLE:
            raise ImportError(
                "sib-api-v3-sdk not installed. "
                "Install with: pip install sib-api-v3-sdk"
            )
        
        if not api_key:
            raise ValueError("Brevo API key is required")
        
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.max_urls_in_email = max_urls_in_email
        self.logger = logging.getLogger(__name__)
        
        # Configure Brevo API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
    
    def _parse_recipients(self, recipient: str) -> List[str]:
        """
        Parse recipient string into list of email addresses
        
        Args:
            recipient: Single email or comma-separated emails
            
        Returns:
            List of email addresses
        """
        if not recipient:
            return []
        
        # Split by comma and clean whitespace
        recipients = [email.strip() for email in recipient.split(',')]
        # Filter out empty strings
        recipients = [email for email in recipients if email]
        
        return recipients
    
    def send_report(
        self,
        recipient: str,
        failed_urls: List[Dict],
        txt_report_path: str,
        json_report_path: str
    ):
        """
        Send email report with attachments
        
        Args:
            recipient: Recipient email address (or comma-separated list)
            failed_urls: List of failed URLs
            txt_report_path: Path to TXT report
            json_report_path: Path to JSON report
        """
        try:
            # Parse recipients
            recipients = self._parse_recipients(recipient)
            
            if not recipients:
                raise ValueError("No valid recipients found")
            
            print(f"📧 EmailSender: Preparing to send email...")
            print(f"   Recipients: {', '.join(recipients)} ({len(recipients)} total)")
            print(f"   Failed URLs: {len(failed_urls)}")
            print(f"   TXT Report: {txt_report_path}")
            print(f"   JSON Report: {json_report_path}")
            
            self.logger.info(f"Sending email to {len(recipients)} recipient(s) with {len(failed_urls)} failed URLs")
            
            # Read report files as base64 for attachments
            print(f"📄 Reading report files...")
            with open(txt_report_path, 'rb') as f:
                txt_content_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            with open(json_report_path, 'rb') as f:
                json_content_b64 = base64.b64encode(f.read()).decode('utf-8')
            
            with open(txt_report_path, 'r', encoding='utf-8') as f:
                txt_content = f.read()
            
            print(f"✓ Report files read successfully")
            
            # Generate HTML body
            print(f"📝 Generating HTML body...")
            html_body = self._generate_html_body(failed_urls)
            print(f"✓ HTML body generated")
            
            # Prepare attachments for Brevo (Brevo doesn't support .json, rename to .txt)
            print(f"📎 Preparing attachments...")
            
            # Read JSON report as text for attachment
            with open(json_report_path, 'r', encoding='utf-8') as f:
                json_content_text = f.read()
            json_content_text_b64 = base64.b64encode(json_content_text.encode('utf-8')).decode('utf-8')
            
            attachments = [
                sib_api_v3_sdk.SendSmtpEmailAttachment(
                    name=os.path.basename(txt_report_path),
                    content=txt_content_b64
                ),
                sib_api_v3_sdk.SendSmtpEmailAttachment(
                    name=os.path.basename(json_report_path).replace('.json', '_data.txt'),  # Rename .json to .txt
                    content=json_content_text_b64
                )
            ]
            print(f"✓ Attachments prepared: {len(attachments)} files")
            
            # Prepare recipients list for Brevo
            to_list = [{"email": email} for email in recipients]
            
            # Prepare and send email via Brevo
            print(f"🚀 Sending email via Brevo...")
            
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                sender={"name": self.sender_name, "email": self.sender_email},
                to=to_list,
                subject=f"⚠️ URL Validation Report - {len(failed_urls)} problematic URLs",
                html_content=html_body,
                text_content=txt_content,
                attachment=attachments
            )
            
            response = self.api_instance.send_transac_email(send_smtp_email)
            print(f"✓ Email sent! Response received")
            
            if response and response.message_id:
                message_id = response.message_id
                print(f"✅ Email successfully sent to {len(recipients)} recipient(s)")
                for email in recipients:
                    print(f"   → {email}")
                print(f"   Message ID: {message_id}")
                self.logger.info(f"Email successfully sent to {len(recipients)} recipient(s), ID: {message_id}")
            else:
                print(f"⚠️  Unexpected response from Brevo API")
                self.logger.warning(f"Unexpected response: {response}")
            
        except ApiException as error:
            error_text = str(error)
            self.logger.error(f"Brevo API error: {error_text}")
            
            # Parse error message for better user feedback
            if 'unauthorized' in error_text.lower() or 'api key' in error_text.lower():
                print(f"\n❌ BREVO API KEY ERROR:")
                print(f"   The API key is invalid or not configured")
                print(f"   Please check your configuration:")
                print(f"   1. Get a free API key at: https://app.brevo.com/settings/keys/api")
                print(f"   2. Update BREVO_API_KEY in environment variables")
                print(f"   3. Or update [BREVO] api_key in config.ini")
            else:
                print(f"❌ Error sending email via Brevo: {error_text}")
            raise
        except Exception as error:
            error_text = str(error)
            self.logger.error(f"Error sending email: {error_text}")
            print(f"❌ Error sending email: {error_text}")
            raise
    
    def _load_email_template(self) -> str:
        """Load email template from file"""
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'email_template.html')
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            self.logger.warning(f"Email template not found at {template_path}, using default")
            # Fallback to simple template
            return """
            <!DOCTYPE html>
            <html>
            <body>
                <h1>URL Validation Report</h1>
                <p>{{FAILED_COUNT}} problematic URLs detected</p>
                <p>Report Date: {{REPORT_DATE}}</p>
                {{FAILED_URLS_TABLE}}
            </body>
            </html>
            """
    
    def _generate_html_body(self, failed_urls: List[Dict]) -> str:
        """Generate HTML email body using template"""
        # Load template
        template = self._load_email_template()
        
        # Generate URLs table
        urls_table_html = ""
        for i, item in enumerate(failed_urls[:self.max_urls_in_email], 1):
            status_code = item.get('status_code', 'N/A')
            url = item.get('url', 'N/A')
            page = item.get('page', 'N/A')
            attempts = item.get('attempts', 1)
            
            # Determine status color
            if status_code == 404:
                status_color = '#dc2626'  # red
            elif status_code >= 500:
                status_color = '#ea580c'  # orange
            else:
                status_color = '#ca8a04'  # yellow
            
            urls_table_html += f"""
                <div style="padding: 15px; border-bottom: 1px solid #e5e7eb;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="padding-bottom: 8px;">
                                <span style="color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">URL #{i}</span>
                            </td>
                            <td style="text-align: right; padding-bottom: 8px;">
                                <span style="background-color: {status_color}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                                    {status_code}
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td colspan="2" style="padding-bottom: 8px;">
                                <a href="{url}" style="color: #667eea; text-decoration: none; font-size: 13px; word-break: break-all;">
                                    {url}
                                </a>
                            </td>
                        </tr>
                        <tr>
                            <td colspan="2">
                                <span style="color: #9ca3af; font-size: 12px;">
                                    Page: {page} • Attempts: {attempts}
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
            """
        
        if len(failed_urls) > self.max_urls_in_email:
            urls_table_html += f"""
                <div style="padding: 15px; background-color: #f9fafb; text-align: center;">
                    <span style="color: #6b7280; font-size: 13px;">
                        ... and {len(failed_urls) - self.max_urls_in_email} more URLs in the attached reports
                    </span>
                </div>
            """
        
        # Replace template variables
        html = template.replace('{{FAILED_COUNT}}', str(len(failed_urls)))
        html = html.replace('{{REPORT_DATE}}', datetime.now().strftime('%B %d, %Y at %H:%M:%S'))
        html = html.replace('{{FAILED_URLS_TABLE}}', urls_table_html)
        
        return html
