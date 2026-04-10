"""
Script to initialize database tables
Run this after installing dependencies: python scripts/init_db.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import create_tables
from config.settings import settings

if __name__ == "__main__":
    print("🚀 Initializing database tables...")
    try:
        create_tables()
        print("✅ Database tables created successfully!")
        print(f"📊 Connected to: {settings.database_url.split('@')[1].split('/')[0]}")
    except Exception as e:
        print(f"❌ Failed to create tables: {str(e)}")
        sys.exit(1)