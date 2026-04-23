"""
Migration: Add subscription/usage columns to users table.

Adds plan_type, subscription_status, stripe_customer_id, and analyses_used
to the local users table (if they don't exist).

Run with: python scripts/migrate_usage_columns.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.models.database import engine


COLUMNS = [
    ("plan_type", "VARCHAR NOT NULL DEFAULT 'basic'"),
    ("subscription_status", "VARCHAR NOT NULL DEFAULT 'inactive'"),
    ("stripe_customer_id", "VARCHAR UNIQUE"),
    ("analyses_used", "INTEGER NOT NULL DEFAULT 0"),
]


def migrate():
    with engine.connect() as conn:
        for col_name, col_def in COLUMNS:
            # Check if column exists
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = :col"
            ), {"col": col_name})

            if result.fetchone():
                print(f"  ✅ Column '{col_name}' already exists — skipping")
            else:
                conn.execute(text(
                    f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                ))
                print(f"  ✅ Column '{col_name}' added successfully")

        conn.commit()
    print("\n🎉 Migration complete!")


if __name__ == "__main__":
    print("🔧 Adding subscription columns to users table...\n")
    migrate()
