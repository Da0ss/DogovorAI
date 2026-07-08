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
        if "@" in settings.database_url:
            db_host = settings.database_url.split('@')[1].split('/')[0]
        else:
            db_host = settings.database_url.split('//')[1].split('/')[0]
        print(f"📊 Connected to: {db_host}")
    except Exception as e:
        print(f"❌ Failed to create tables: {str(e)}")
        sys.exit(1)