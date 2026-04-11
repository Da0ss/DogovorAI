"""
Email sending service using SMTP.
"""

import logging
import smtplib
from email.message import EmailMessage
from config.settings import settings

logger = logging.getLogger(__name__)


def send_verification_code_email(email: str, code: str) -> None:
    """Send verification code to the user's email."""
    # For local testing, use simple SMTP without auth
    if not settings.email_host:
        logger.warning("⚠️ Email host not configured, skipping email send")
        return

    message = EmailMessage()
    message["Subject"] = f"{settings.app_name}: код подтверждения"
    message["From"] = settings.email_from or "test@localhost"
    message["To"] = email
    message.set_content(
        f"Здравствуйте!\n\nВаш код подтверждения для {settings.app_name}: {code}\n\n"
        "Если вы не запрашивали код, просто игнорируйте это письмо.\n\n"
        f"С уважением,\nКоманда {settings.app_name}"
    )
    message.add_alternative(
        f"<html><body>"
        f"<p>Здравствуйте!</p>"
        f"<p>Ваш код подтверждения для <strong>{settings.app_name}</strong>: "
        f"<strong>{code}</strong></p>"
        f"<p>Если вы не запрашивали код, просто игнорируйте это письмо.</p>"
        f"<p>С уважением,<br>Команда {settings.app_name}</p>"
        f"</body></html>",
        subtype="html"
    )

    try:
        # Use simple SMTP for local testing
        with smtplib.SMTP(settings.email_host, settings.email_port, timeout=30) as smtp:
            smtp.send_message(message)
            logger.info(f"✅ Email sent to {email} with code {code}")
    except Exception as e:
        logger.error(f"❌ Failed to send email: {str(e)}")
        # For testing, also print the code to console
        print(f"📧 TEST MODE: Verification code for {email}: {code}")
