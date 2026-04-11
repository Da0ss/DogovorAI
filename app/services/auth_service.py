"""
Supabase Auth service for user registration and verification.
"""

import logging
import os
from typing import Optional, Dict, Any
from supabase import Client
from config.database import get_supabase_client
from config.settings import settings

logger = logging.getLogger(__name__)

# Import local services for testing
try:
    from app.services.verification_service import get_verification_service
    from app.services.email_service import send_verification_code_email
    # Локальный режим только при полной настройке SMTP; в pytest — ветка Supabase (моки)
    LOCAL_MODE = (
        settings.email_configured
        and os.environ.get("PYTEST_RUNNING") != "1"
    )
    logger.info(f"🔧 Local mode: {LOCAL_MODE}, email_configured: {settings.email_configured}")
except ImportError as e:
    LOCAL_MODE = False
    logger.warning(f"⚠️ Local verification services not available: {e}")


class SupabaseAuthService:
    """
    Service for handling user authentication via Supabase Auth.
    """

    def __init__(self):
        # Клиент будет получаться лениво для поддержки моков в тестах
        self._client = None

    @property
    def client(self) -> Client:
        """Get Supabase client with lazy initialization."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def register_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user.

        Args:
            email: User email
            password: User password

        Returns:
            Dict containing user data and session info

        Raises:
            Exception: If registration fails
        """
        if LOCAL_MODE:
            # Local testing mode - skip Supabase registration
            logger.info(f"🔧 Local mode: Registering user {email} locally")

            # Generate verification code
            verification_service = get_verification_service()
            code = verification_service.generate_code(email)

            # Send email
            try:
                send_verification_code_email(email, code)
                logger.info(f"✅ Local verification code sent to {email}: {code}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send local email: {str(e)}")
                print(f"📧 TEST MODE: Verification code for {email}: {code}")

            # Return mock response
            return {
                "user": {
                    "id": f"local-{hash(email) % 10000}",
                    "email": email,
                    "email_confirmed_at": None
                }
            }
        else:
            # Production mode - use Supabase
            try:
                response = self.client.auth.sign_up({
                    "email": email,
                    "password": password
                })
                logger.info(f"✅ User registered via Supabase Auth: {email}")
                return response
            except Exception as e:
                logger.error(f"❌ Supabase Auth registration failed: {str(e)}")
                raise

    def verify_email(self, email: str, token: str) -> Dict[str, Any]:
        """
        Verify user email with token.

        Args:
            email: User email
            token: Verification token/code

        Returns:
            Dict containing verification result

        Raises:
            Exception: If verification fails
        """
        if LOCAL_MODE:
            # Use local verification
            verification_service = get_verification_service()
            if verification_service.verify_code(email, token):
                return {"user": {"id": f"local-{email}", "email": email, "email_confirmed_at": "now"}}
            else:
                raise Exception("Invalid verification code")
        else:
            # Use Supabase
            try:
                response = self.client.auth.verify_otp({
                    "email": email,
                    "token": token,
                    "type": "email"
                })
                logger.info(f"✅ Email verified via Supabase Auth: {email}")
                return response
            except Exception as e:
                logger.error(f"❌ Supabase Auth verification failed: {str(e)}")
                raise

    def resend_verification_code(self, email: str) -> Dict[str, Any]:
        """
        Resend verification code to email.

        Args:
            email: User email

        Returns:
            Dict containing resend result

        Raises:
            Exception: If resend fails
        """
        if LOCAL_MODE:
            # Generate new code and send via local email
            verification_service = get_verification_service()
            code = verification_service.generate_code(email)
            try:
                send_verification_code_email(email, code)
                return {"message": "Code sent successfully"}
            except Exception as e:
                logger.error(f"❌ Local email send failed: {str(e)}")
                raise Exception(f"Failed to send email: {str(e)}")
        else:
            # Use Supabase
            try:
                response = self.client.auth.resend({
                    "email": email,
                    "type": "signup"
                })
                logger.info(f"✅ Verification code resent via Supabase Auth: {email}")
                return response
            except Exception as e:
                logger.error(f"❌ Supabase Auth resend failed: {str(e)}")
                raise

    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            Dict containing session data

        Raises:
            Exception: If login fails
        """
        logger.info(f"🔧 Login attempt - Local mode: {LOCAL_MODE}")
        if LOCAL_MODE:
            # Local testing mode - mock login
            logger.info(f"✅ User logged in locally: {email}")
            return {
                "user": {
                    "id": f"local-{hash(email) % 10000}",
                    "email": email,
                    "email_confirmed_at": "now"
                },
                "session": {
                    "access_token": f"local-token-{hash(email)}",
                    "refresh_token": f"local-refresh-{hash(email)}"
                }
            }
        else:
            # Production mode - use Supabase
            logger.info(f"🔧 Using Supabase login for {email}")
            try:
                response = self.client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                logger.info(f"✅ User logged in via Supabase Auth: {email}")
                return response
            except Exception as e:
                logger.error(f"❌ Supabase Auth login failed: {str(e)}")
                raise


# Global instance
auth_service = SupabaseAuthService()


async def get_auth_service() -> SupabaseAuthService:
    """
    Get Supabase Auth service instance.

    Returns:
        SupabaseAuthService: Auth service instance
    """
    return auth_service