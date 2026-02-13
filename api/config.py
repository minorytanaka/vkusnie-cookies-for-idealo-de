from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DB_URL")  # Теперь из .env (PostgreSQL)
if not DB_URL:
    raise ValueError("DB_URL не найден в .env файле")
