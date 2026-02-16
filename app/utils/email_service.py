"""Email service utility using aiosmtplib."""
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Union
import aiosmtplib
from app.config import get_settings

logger = logging.getLogger(__name__)

async def send_email(
    subject: str,
    recipients: Union[str, List[str]],
    html_content: str,
    text_content: Optional[str] = None
):
    """
    Sends an email asynchronously using SMTP settings from config.
    """
    settings = get_settings()
    
    if isinstance(recipients, str):
        recipients = [recipients]

    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = ", ".join(recipients)

    if text_content:
        part1 = MIMEText(text_content, "plain")
        message.attach(part1)
    
    part2 = MIMEText(html_content, "html")
    message.attach(part2)

    try:
        smtp_options = {
            "hostname": settings.SMTP_SERVER,
            "port": settings.SMTP_PORT,
            "use_tls": settings.SMTP_TLS,
        }
        
        async with aiosmtplib.SMTP(**smtp_options) as smtp:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            await smtp.send_message(message)
            logger.info(f"Email sent successfully to {recipients}")
            return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise e
