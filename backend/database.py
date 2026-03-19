import os

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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


class ResearchRun(Base):
    __tablename__ = "research_runs"

    run_id = Column(String, primary_key=True)
    request_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    market = Column(String, nullable=True, index=True)
    symbols_json = Column(Text, nullable=False, default="[]")
    strategy_type = Column(String, nullable=True)
    runtime_mode = Column(String, nullable=True, index=True)
    default_bundle_version = Column(String, nullable=True)
    effective_threshold = Column(Float, nullable=True)
    effective_top_n = Column(Integer, nullable=True)
    allow_proactive_sells = Column(Boolean, nullable=True)
    config_sources_json = Column(Text, nullable=True)
    fallback_audit_json = Column(Text, nullable=True)
    validation_outcome_json = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    request_payload_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    warnings_json = Column(Text, nullable=True)
    threshold_policy_version = Column(String, nullable=True)
    price_basis_version = Column(String, nullable=True)
    benchmark_comparability_gate = Column(Boolean, nullable=True)
    comparison_eligibility = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class NormalizedReplayRun(Base):
    __tablename__ = "normalized_replay_runs"

    id = Column(Integer, primary_key=True)
    raw_payload_id = Column(Integer, nullable=False, index=True)
    source_name = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    archive_object_reference = Column(String, nullable=True)
    parser_version = Column(String, nullable=False)
    benchmark_profile_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    restore_status = Column(String, nullable=False, index=True)
    abort_reason = Column(Text, nullable=True)
    restored_row_count = Column(Integer, nullable=False, default=0)
    replay_started_at = Column(DateTime(timezone=True), nullable=False)
    replay_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class RecoveryDrill(Base):
    __tablename__ = "recovery_drills"

    id = Column(Integer, primary_key=True)
    raw_payload_id = Column(Integer, nullable=False, index=True)
    replay_run_id = Column(Integer, nullable=True, index=True)
    benchmark_profile_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, index=True)
    latest_replayable_day = Column(Date, nullable=True)
    completed_trading_day_delta = Column(Integer, nullable=True)
    abort_reason = Column(Text, nullable=True)
    drill_started_at = Column(DateTime(timezone=True), nullable=False)
    drill_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SymbolLifecycleRecord(Base):
    __tablename__ = "symbol_lifecycle_records"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "market",
            "event_type",
            "effective_date",
            name="uq_symbol_lifecycle_record",
        ),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    effective_date = Column(Date, nullable=False, index=True)
    reference_symbol = Column(String, nullable=True)
    source_name = Column(String, nullable=False)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    archive_object_reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ImportantEvent(Base):
    __tablename__ = "important_events"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "market",
            "event_type",
            "event_publication_ts",
            name="uq_important_event",
        ),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    effective_date = Column(Date, nullable=True, index=True)
    event_publication_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    timestamp_source_class = Column(String, nullable=False)
    source_name = Column(String, nullable=False)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    archive_object_reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


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
