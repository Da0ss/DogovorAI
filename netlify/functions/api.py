import sys
import os
from pathlib import Path
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def handler(request):
    data = supabase.table("your_table").select("*").execute()
    return {
        "statusCode": 200,
        "body": str(data)
    }

# Добавляем корень проекта в sys.path, чтобы импортировать main и app
root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.append(root_dir)

import mangum
from main import app

# Создаём обработчик для AWS Lambda / Netlify Functions
# lifespan="on" позволяет выполнять код из @asynccontextmanager lifespan
handler = mangum.Mangum(app, lifespan="on")
