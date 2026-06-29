"""add consent_accepted columns to profiles

Revision ID: 002_add_consent
Revises: 001_initial
Create Date: 2026-06-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_consent'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add consent tracking columns to profiles table."""
    op.add_column('profiles', sa.Column('consent_accepted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('profiles', sa.Column('consent_accepted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove consent tracking columns from profiles table."""
    op.drop_column('profiles', 'consent_accepted_at')
    op.drop_column('profiles', 'consent_accepted')
