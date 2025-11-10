# backend/app/db/base.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retry connecting to the database on startup
for _ in range(5):
    try:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        engine.connect()
        logger.info("Database connection successful.")
        break
    except Exception as e:
        logger.error(f"Database connection failed: {e}. Retrying in 5 seconds...")
        time.sleep(5)
else:
    logger.critical("Could not connect to the database after several retries.")
    exit(1)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()