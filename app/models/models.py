"""
SQLAlchemy models for DogovorAI database.

Таблица: profiles (не users!) — синхронизировано с Supabase.
  - id: UUID строка (совместимо с auth.users в Supabase)
  - hashed_password: nullable (NULL для Google/OTP OAuth-пользователей)
  - verification_codes: связь по UUID
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def _new_uuid() -> str:
    """Генерирует новый UUID v4 в виде строки."""
    return str(uuid.uuid4())


class User(Base):
    """
    Профиль пользователя. Таблица: public.profiles.

    Совместима с Supabase:
      - id = UUID (строка). Для Supabase-Auth пользователей совпадает с auth.users.id.
      - hashed_password = NULL для Google/OTP OAuth пользователей.
    """
    __tablename__ = "profiles"

    id                  = Column(String, primary_key=True, default=_new_uuid, index=True)
    email               = Column(String, unique=True, index=True, nullable=False)
    hashed_password     = Column(String, nullable=True)   # NULL для OAuth-пользователей
    is_verified         = Column(Boolean, default=False)
    full_name           = Column(String, nullable=True)
    avatar_url          = Column(String, nullable=True)
    auth_provider       = Column(String, default="local", nullable=False)  # local | google | otp

    # Subscription
    plan_type           = Column(String, default="basic", nullable=False)
    subscription_status = Column(String, default="inactive", nullable=False)
    stripe_customer_id  = Column(String, unique=True, nullable=True)

    # Usage tracking
    analyses_used       = Column(Integer, default=0, nullable=False)
    analyses_limit      = Column(Integer, default=3, nullable=True)  # NULL = безлимит (Max)
    analyses_reset_at   = Column(DateTime, nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to verification codes
    verification_codes = relationship("VerificationCode", back_populates="user",
                                      cascade="all, delete-orphan")


class VerificationCode(Base):
    """Коды верификации email и OTP входа."""
    __tablename__ = "verification_codes"

    id          = Column(String, primary_key=True, default=_new_uuid)
    user_id     = Column(String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    code        = Column(String(6), nullable=False)
    purpose     = Column(String, default="email_verify", nullable=False)  # email_verify | otp_login
    is_used     = Column(Boolean, default=False, nullable=False)
    expires_at  = Column(DateTime, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Relationship to user
    user = relationship("User", back_populates="verification_codes")


class Document(Base):
    """
    Информация о загруженном пользователем документе. Таблица: public.documents.
    """
    __tablename__ = "documents"

    id              = Column(String, primary_key=True, default=_new_uuid, index=True)
    user_id         = Column(String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    filename        = Column(String, nullable=False)
    original_name   = Column(String, nullable=False)
    file_type       = Column(String, nullable=False)
    file_size_bytes = Column(Integer, default=0)
    char_count      = Column(Integer, default=0)
    page_count      = Column(Integer, default=0)
    storage_path    = Column(String, nullable=True)
    storage_bucket  = Column(String, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    analysis_results = relationship("AnalysisResult", back_populates="document", cascade="all, delete-orphan")


class AnalysisResult(Base):
    """
    Результат анализа документа. Таблица: public.analysis_results.
    """
    __tablename__ = "analysis_results"

    id                  = Column(String, primary_key=True, default=_new_uuid, index=True)
    user_id             = Column(String, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    document_id         = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_type       = Column(String, nullable=True)
    summary             = Column(String, nullable=True)
    overall_risk_level  = Column(String, nullable=True)
    risks               = Column(JSONB, nullable=True, default=list) # [{category, description, risk_level...}]
    recommendations     = Column(JSONB, nullable=True, default=list) # [str]
    total_risks         = Column(Integer, default=0)
    high_risk_count     = Column(Integer, default=0)
    medium_risk_count   = Column(Integer, default=0)
    ai_tokens_used      = Column(Integer, default=0)
    success             = Column(Boolean, default=True)
    error_message       = Column(String, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    document = relationship("Document", back_populates="analysis_results")