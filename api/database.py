from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import DB_URL

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)  # Создание таблицы (если нет)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()