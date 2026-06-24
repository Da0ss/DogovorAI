"""
Supabase Auth service for user registration and verification.
"""

import logging
import os
from typing import Optional, Dict, Any
try:
    from supabase import Client
except ImportError:
    Client = object  # type: ignore

from config.database import get_supabase_client
from config.settings import settings
from app.services.auth_context import is_debug_or_test

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
        """Get a fresh Supabase client instance."""
        return get_supabase_client()

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
                if is_debug_or_test():
                    logger.info(f"📧 TEST MODE: Verification code for {email}: {code}")

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

    def send_login_otp(self, email: str) -> Dict[str, Any]:
        """
        Send a one-time password (OTP) via email for passwordless login.

        Args:
            email: User email

        Returns:
            Dict containing the response from Supabase

        Raises:
            Exception: If sending OTP fails
        """
        logger.info(f"🔧 OTP send attempt - Local mode: {LOCAL_MODE}")
        if LOCAL_MODE:
            # Local testing mode - just mock success or use local service
            verification_service = get_verification_service()
            code = verification_service.generate_code(email)
            try:
                send_verification_code_email(email, code)
                logger.info(f"✅ Local OTP code sent to {email}: {code}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send local email: {str(e)}")
                if is_debug_or_test():
                    logger.info(f"📧 TEST MODE: OTP Code for {email}: {code}")

            return {"message": "OTP code sent via local auth"}
        else:
            # Production mode - use Supabase OTP
            logger.info(f"🔧 Using Supabase OTP for {email}")
            try:
                response = self.client.auth.sign_in_with_otp({
                    "email": email,
                    "options": {
                        "should_create_user": True
                    }
                })
                logger.info(f"✅ OTP sent via Supabase Auth to: {email}")
                return response
            except Exception as e:
                logger.error(f"❌ Supabase Auth OTP send failed: {str(e)}")
                raise

    def verify_login_otp(self, email: str, token: str) -> Dict[str, Any]:
        """
        Verify the OTP token for login.

        Args:
            email: User email
            token: Verification token/code

        Returns:
            Dict containing session data and user info

        Raises:
            Exception: If verification fails
        """
        if LOCAL_MODE:
            # Use local verification
            verification_service = get_verification_service()
            if verification_service.verify_code(email, token):
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
                raise Exception("Invalid OTP code")
        else:
            # Use Supabase
            try:
                response = self.client.auth.verify_otp({
                    "email": email,
                    "token": token,
                    "type": "email"
                })
                logger.info(f"✅ OTP verified via Supabase Auth for: {email}")

                # Extract user and session data similarly to Google OAuth callback
                user_data = None
                session_data = None

                if hasattr(response, 'user') and response.user:
                    user = response.user
                    user_data = {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": (
                            user.user_metadata.get("full_name")
                            or user.user_metadata.get("name", "")
                        ) if user.user_metadata else "",
                        "avatar_url": (
                            user.user_metadata.get("avatar_url")
                            or user.user_metadata.get("picture", "")
                        ) if user.user_metadata else "",
                        "is_verified": True
                    }

                if hasattr(response, 'session') and response.session:
                    session = response.session
                    session_data = {
                        "access_token": session.access_token,
                        "refresh_token": session.refresh_token,
                        "expires_in": session.expires_in,
                        "token_type": "bearer"
                    }

                return {
                    "user": user_data,
                    "session": session_data
                }
            except Exception as e:
                logger.error(f"❌ Supabase Auth OTP verification failed: {str(e)}")
                raise

    # ================================================================
    # Google OAuth Methods
    # ================================================================

    def sign_in_with_google(self, redirect_to: str) -> Dict[str, Any]:
        """
        Generate Google OAuth URL via Supabase Auth.

        Args:
            redirect_to: URL to redirect after successful auth

        Returns:
            Dict with 'url' key containing the Google OAuth URL and optional 'code_verifier'

        Raises:
            Exception: If URL generation fails
        """
        try:
            client = self.client
            response = client.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": redirect_to,
                    "query_params": {
                        "access_type": "offline",
                        "prompt": "consent"
                    }
                }
            })

            # Extract code verifier from client storage
            code_verifier = None
            try:
                storage_key = f"{client.auth._storage_key}-code-verifier"
                code_verifier = client.auth._storage.get_item(storage_key)
            except Exception as se:
                logger.warning(f"⚠️ Could not extract code verifier: {se}")

            logger.info("✅ Google OAuth URL generated")

            url = None
            if hasattr(response, 'url'):
                url = response.url
            elif isinstance(response, dict):
                url = response.get('url')

            return {
                "url": url,
                "code_verifier": code_verifier
            }
        except Exception as e:
            logger.error(f"❌ Google OAuth URL generation failed: {str(e)}")
            raise

    def exchange_code_for_session(self, code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange authorization code for a Supabase session.

        Args:
            code: Authorization code from OAuth callback
            code_verifier: Optional PKCE code verifier

        Returns:
            Dict containing session and user data

        Raises:
            Exception: If code exchange fails
        """
        try:
            params = {
                "auth_code": code
            }
            if code_verifier:
                params["code_verifier"] = code_verifier

            response = self.client.auth.exchange_code_for_session(params)
            logger.info("✅ OAuth code exchanged for session")

            # Extract user and session data
            user_data = None
            session_data = None

            if hasattr(response, 'user') and response.user:
                user = response.user
                user_data = {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": (
                        user.user_metadata.get("full_name")
                        or user.user_metadata.get("name", "")
                    ) if user.user_metadata else "",
                    "avatar_url": (
                        user.user_metadata.get("avatar_url")
                        or user.user_metadata.get("picture", "")
                    ) if user.user_metadata else "",
                    "is_verified": True
                }

            if hasattr(response, 'session') and response.session:
                session = response.session
                session_data = {
                    "access_token": session.access_token,
                    "refresh_token": session.refresh_token,
                    "expires_in": session.expires_in,
                    "token_type": "bearer"
                }

            return {
                "user": user_data,
                "session": session_data
            }
        except Exception as e:
            logger.error(f"❌ OAuth code exchange failed: {str(e)}")
            raise

    def get_user_profile(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile data from Supabase using access token.

        Args:
            access_token: JWT access token

        Returns:
            Dict with user profile data or None
        """
        try:
            response = self.client.auth.get_user(access_token)

            if hasattr(response, 'user') and response.user:
                user = response.user
                metadata = user.user_metadata or {}
                return {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": metadata.get("full_name") or metadata.get("name", ""),
                    "avatar_url": metadata.get("avatar_url") or metadata.get("picture", ""),
                    "is_verified": user.email_confirmed_at is not None
                }
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get user profile: {str(e)}")
            return None

    def sign_out(self, access_token: str) -> bool:
        """
        Sign out user by invalidating their Supabase session.

        Args:
            access_token: JWT access token to invalidate

        Returns:
            bool: True if sign out was successful
        """
        try:
            self.client.auth.admin.sign_out(access_token)
            logger.info("✅ User signed out successfully")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Sign out via admin failed, trying client: {str(e)}")
            try:
                # Fallback: just return True (client-side will clear tokens)
                return True
            except Exception as e2:
                logger.error(f"❌ Sign out failed: {str(e2)}")
                return False


# Global instance
auth_service = SupabaseAuthService()


async def get_auth_service() -> SupabaseAuthService:
    """
    Get Supabase Auth service instance.

    Returns:
        SupabaseAuthService: Auth service instance
    """
    return auth_service
