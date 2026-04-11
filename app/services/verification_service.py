"""
Simple verification code storage for local testing
"""

import random
import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VerificationCode:
    """Verification code data"""
    code: str
    email: str
    created_at: float
    expires_at: float
    used: bool = False


class LocalVerificationService:
    """
    Local verification service for testing without Supabase rate limits
    """

    def __init__(self):
        self.codes: Dict[str, VerificationCode] = {}
        self.code_expiry = 600  # 10 minutes

    def generate_code(self, email: str) -> str:
        """
        Generate and store verification code for email

        Args:
            email: User email

        Returns:
            str: Generated verification code
        """
        # Generate 6-digit code
        code = str(random.randint(100000, 999999))

        # Store code
        now = time.time()
        verification = VerificationCode(
            code=code,
            email=email,
            created_at=now,
            expires_at=now + self.code_expiry
        )

        self.codes[email] = verification

        logger.info(f"✅ Generated verification code for {email}: {code}")
        return code

    def verify_code(self, email: str, code: str) -> bool:
        """
        Verify code for email

        Args:
            email: User email
            code: Verification code

        Returns:
            bool: Verification success
        """
        if email not in self.codes:
            logger.warning(f"❌ No verification code found for {email}")
            return False

        verification = self.codes[email]

        # Check if code is expired
        if time.time() > verification.expires_at:
            logger.warning(f"❌ Verification code expired for {email}")
            del self.codes[email]
            return False

        # Check if code matches
        if verification.code != code:
            logger.warning(f"❌ Invalid verification code for {email}")
            return False

        # Mark as used
        verification.used = True
        logger.info(f"✅ Email verified successfully for {email}")
        return True

    def get_pending_code(self, email: str) -> Optional[str]:
        """
        Get pending verification code for testing

        Args:
            email: User email

        Returns:
            Optional[str]: Verification code if exists and not expired
        """
        if email not in self.codes:
            return None

        verification = self.codes[email]
        if time.time() > verification.expires_at or verification.used:
            return None

        return verification.code


# Global instance
verification_service = LocalVerificationService()


def get_verification_service() -> LocalVerificationService:
    """
    Get verification service instance

    Returns:
        LocalVerificationService: Verification service instance
    """
    return verification_service