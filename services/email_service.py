"""
Email Service for sending emails via SMTP.
Supports Gmail, Outlook, SendGrid, AWS SES, and other SMTP providers.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from config import SMTPConfig, FeatureFlags

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""
    
    def __init__(self):
        self.host = SMTPConfig.SMTP_HOST
        self.port = SMTPConfig.SMTP_PORT
        self.user = SMTPConfig.SMTP_USER
        self.password = SMTPConfig.SMTP_PASSWORD
        self.from_email = SMTPConfig.SMTP_FROM_EMAIL
        self.from_name = SMTPConfig.SMTP_FROM_NAME
        self.use_tls = SMTPConfig.SMTP_USE_TLS
        self.use_ssl = SMTPConfig.SMTP_USE_SSL
        self._server: Optional[smtplib.SMTP] = None
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return SMTPConfig.is_configured() and FeatureFlags.EMAIL_ENABLED
    
    def _connect(self) -> smtplib.SMTP:
        """Establish connection to SMTP server."""
        try:
            if self.use_ssl:
                # SSL connection (port 465 typically)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.host, self.port, context=context)
            else:
                # Standard connection with optional TLS (port 587 typically)
                server = smtplib.SMTP(self.host, self.port)
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            # Login
            server.login(self.user, self.password)
            logger.info(f"Connected to SMTP server: {self.host}:{self.port}")
            return server
        except Exception as e:
            logger.error(f"Failed to connect to SMTP server: {e}")
            raise
    
    def _disconnect(self, server: smtplib.SMTP):
        """Close SMTP connection."""
        try:
            server.quit()
            logger.info("Disconnected from SMTP server")
        except Exception as e:
            logger.warning(f"Error disconnecting from SMTP: {e}")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Path]] = None,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body (for rich formatting)
            cc: List of CC recipients
            bcc: List of BCC recipients
            attachments: List of file paths to attach
            reply_to: Reply-to email address
        
        Returns:
            Dict with success status and message
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Email service is not configured. Please set SMTP credentials in .env"
            }
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to
            
            # Add plain text body
            msg.attach(MIMEText(body, "plain"))
            
            # Add HTML body if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={file_path.name}"
                            )
                            msg.attach(part)
            
            # Build recipient list
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Connect and send
            server = self._connect()
            try:
                server.sendmail(self.from_email, recipients, msg.as_string())
                logger.info(f"Email sent successfully to {to_email}")
                return {
                    "success": True,
                    "message": f"Email sent to {to_email}",
                    "subject": subject
                }
            finally:
                self._disconnect(server)
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {e}")
            return {
                "success": False,
                "error": "Authentication failed. Check your SMTP username and password."
            }
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipients refused: {e}")
            return {
                "success": False,
                "error": f"Invalid recipient email: {to_email}"
            }
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_contact_email(
        self,
        contact_email: str,
        contact_name: str,
        subject: str,
        message: str,
        template: str = "default"
    ) -> Dict[str, Any]:
        """
        Send a templated email to a contact.
        
        Args:
            contact_email: Contact's email address
            contact_name: Contact's name for personalization
            subject: Email subject
            message: Main message content
            template: Template style (default, formal, casual)
        
        Returns:
            Dict with success status
        """
        # Build HTML email with template
        if template == "formal":
            html_body = f"""
            <html>
            <body style="font-family: Georgia, serif; color: #333; max-width: 600px; margin: 0 auto;">
                <p>Dear {contact_name},</p>
                <div style="margin: 20px 0; line-height: 1.6;">
                    {message.replace(chr(10), '<br>')}
                </div>
                <p>Best regards,<br>{self.from_name}</p>
            </body>
            </html>
            """
        elif template == "casual":
            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
                <p>Hey {contact_name}! 👋</p>
                <div style="margin: 20px 0; line-height: 1.6;">
                    {message.replace(chr(10), '<br>')}
                </div>
                <p>Cheers,<br>{self.from_name}</p>
            </body>
            </html>
            """
        else:  # default
            html_body = f"""
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
                    <h2 style="color: white; margin: 0;">{subject}</h2>
                </div>
                <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px;">
                    <p>Hi {contact_name},</p>
                    <div style="margin: 20px 0; line-height: 1.6;">
                        {message.replace(chr(10), '<br>')}
                    </div>
                    <p style="margin-top: 30px;">Best,<br><strong>{self.from_name}</strong></p>
                </div>
            </body>
            </html>
            """
        
        plain_body = f"Hi {contact_name},\n\n{message}\n\nBest,\n{self.from_name}"
        
        return self.send_email(
            to_email=contact_email,
            subject=subject,
            body=plain_body,
            html_body=html_body
        )
    
    def send_follow_up_email(
        self,
        contact_email: str,
        contact_name: str,
        last_interaction: str,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a follow-up email to a contact.
        
        Args:
            contact_email: Contact's email
            contact_name: Contact's name
            last_interaction: Description of last interaction for context
            custom_message: Optional custom message to include
        
        Returns:
            Dict with success status
        """
        subject = f"Following up - {contact_name}"
        
        message = custom_message or f"""
I hope this email finds you well! I wanted to follow up on our previous conversation.

{last_interaction}

I'd love to reconnect and hear how things are going on your end. Let me know if you have some time for a quick chat.

Looking forward to hearing from you!
        """.strip()
        
        return self.send_contact_email(
            contact_email=contact_email,
            contact_name=contact_name,
            subject=subject,
            message=message,
            template="casual"
        )
    
    def send_introduction_email(
        self,
        to_email: str,
        to_name: str,
        intro_person_name: str,
        intro_person_email: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Send an introduction email connecting two contacts.
        
        Args:
            to_email: Primary recipient email
            to_name: Primary recipient name
            intro_person_name: Person being introduced
            intro_person_email: Email of person being introduced
            context: Context for the introduction
        
        Returns:
            Dict with success status
        """
        subject = f"Introduction: {intro_person_name}"
        
        message = f"""
I wanted to introduce you to {intro_person_name} ({intro_person_email}).

{context}

I think you two would have a great conversation! I'll let you take it from here.
        """.strip()
        
        return self.send_contact_email(
            contact_email=to_email,
            contact_name=to_name,
            subject=subject,
            message=message,
            template="default"
        )
    
    def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection without sending an email."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "Email service is not configured"
            }
        
        try:
            server = self._connect()
            self._disconnect(server)
            return {
                "success": True,
                "message": f"Successfully connected to {self.host}:{self.port}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
email_service = EmailService()
