import os

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

# --- Database Configuration ---
# Load database connection details from environment variables with defaults
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
# Use 'localhost' for host scripts, 'db' for dockerized app
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "quant_platform")

# Database URL format: postgresql://user:password@host:port/database
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --- SQLAlchemy Setup ---
# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for declarative models
Base = declarative_base()


# --- ORM Model Definition ---
# Define the DailyOHLCV model
class DailyOHLCV(Base):
    __tablename__ = "daily_ohlcv"
    __table_args__ = (Index("idx_daily_ohlcv_symbol_date", "symbol", "date"),)

    date = Column(Date, primary_key=True)
    symbol = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True, default="unknown")
    market = Column(String, nullable=False, index=True, default="TW")
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    archive_object_reference = Column(String, nullable=True)
    parser_version = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RawIngestAudit(Base):
    __tablename__ = "raw_ingest_audit"

    id = Column(Integer, primary_key=True)
    source_name = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False)
    parser_version = Column(String, nullable=False)
    fetch_status = Column(String, nullable=False)
    expected_symbol_context = Column(String, nullable=False)
    payload_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# --- Database Session Management ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Table Creation ---
# Optional: Create all tables in the database
# This is typically done once at the beginning of your application's lifecycle.
def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    # Use `alembic upgrade head` to create/migrate tables.
    print("Run 'uv run alembic upgrade head' to create or migrate database tables.")
