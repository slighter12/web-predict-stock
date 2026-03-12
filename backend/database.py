import os

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

# --- Database Configuration ---
# Load database connection details from environment variables with defaults
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost") # Use 'localhost' for host scripts, 'db' for dockerized app
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
    __table_args__ = (
        Index("idx_daily_ohlcv_symbol_date", "symbol", "date"),
    )

    date = Column(Date, primary_key=True)
    symbol = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True, default="unknown")
    market = Column(String, nullable=False, index=True, default="TW")
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
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
    # This will create the tables if you run this script directly
    print("Creating database tables...")
    create_tables()
    print("Tables created successfully.")
