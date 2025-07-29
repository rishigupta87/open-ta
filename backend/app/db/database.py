from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use TimescaleDB for everything
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:trading123@timescaledb:5432/trading_data")

engine = create_engine(DATABASE_URL, echo=False)  # Set echo=True for SQL debugging
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()