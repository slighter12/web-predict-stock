import os

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
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
    investability_screening_active = Column(Boolean, nullable=True)
    capacity_screening_active = Column(Boolean, nullable=True)
    capacity_screening_version = Column(String, nullable=True)
    adv_basis_version = Column(String, nullable=True)
    missing_feature_policy_version = Column(String, nullable=True)
    execution_cost_model_version = Column(String, nullable=True)
    split_policy_version = Column(String, nullable=True)
    bootstrap_policy_version = Column(String, nullable=True)
    ic_overlap_policy_version = Column(String, nullable=True)
    comparison_review_matrix_version = Column(String, nullable=True)
    scheduled_review_cadence = Column(String, nullable=True)
    model_family = Column(String, nullable=True, index=True)
    training_output_contract_version = Column(String, nullable=True)
    adoption_comparison_policy_version = Column(String, nullable=True)
    factor_catalog_version = Column(String, nullable=True, index=True)
    scoring_factor_ids_json = Column(Text, nullable=True)
    external_signal_policy_version = Column(String, nullable=True)
    external_lineage_version = Column(String, nullable=True)
    cluster_snapshot_version = Column(String, nullable=True)
    peer_policy_version = Column(String, nullable=True)
    peer_comparison_policy_version = Column(String, nullable=True)
    execution_route = Column(String, nullable=True, index=True)
    simulation_profile_id = Column(String, nullable=True, index=True)
    simulation_adapter_version = Column(String, nullable=True)
    live_control_profile_id = Column(String, nullable=True, index=True)
    live_control_version = Column(String, nullable=True)
    adaptive_mode = Column(String, nullable=True, index=True)
    adaptive_profile_id = Column(String, nullable=True, index=True)
    adaptive_contract_version = Column(String, nullable=True)
    reward_definition_version = Column(String, nullable=True)
    state_definition_version = Column(String, nullable=True)
    rollout_control_version = Column(String, nullable=True)
    tradability_state = Column(String, nullable=True)
    tradability_contract_version = Column(String, nullable=True)
    missing_feature_policy_state = Column(String, nullable=True)
    corporate_event_state = Column(String, nullable=True)
    full_universe_count = Column(Integer, nullable=True)
    execution_universe_count = Column(Integer, nullable=True)
    execution_universe_ratio = Column(Float, nullable=True)
    liquidity_bucket_schema_version = Column(String, nullable=True)
    stale_mark_days_with_open_positions = Column(Integer, nullable=True)
    stale_risk_share = Column(Float, nullable=True)
    monitor_profile_id = Column(String, nullable=True, index=True)
    monitor_observation_status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ResearchRunLiquidityCoverage(Base):
    __tablename__ = "research_run_liquidity_coverages"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "bucket_key",
            name="uq_research_run_liquidity_coverages_run_bucket",
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket_key = Column(String, nullable=False)
    bucket_label = Column(String, nullable=False)
    full_universe_count = Column(Integer, nullable=False, default=0)
    execution_universe_count = Column(Integer, nullable=False, default=0)
    full_universe_ratio = Column(Float, nullable=False, default=0.0)
    execution_coverage_ratio = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class MicrostructureObservation(Base):
    __tablename__ = "microstructure_observations"
    __table_args__ = (
        UniqueConstraint(
            "monitor_profile_id",
            "market",
            "trading_date",
            name="uq_microstructure_observations_profile_market_date",
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monitor_profile_id = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    full_universe_count = Column(Integer, nullable=False, default=0)
    execution_universe_count = Column(Integer, nullable=False, default=0)
    execution_universe_ratio = Column(Float, nullable=False, default=0.0)
    stale_mark_with_open_positions = Column(Boolean, nullable=False, default=False)
    liquidity_bucket_schema_version = Column(String, nullable=False)
    bucket_coverages_json = Column(Text, nullable=False, default="[]")
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
    # NOTE: Both schedule_id and scheduled_for_date are nullable.  In
    # PostgreSQL (and SQLite) NULL values are not considered equal for
    # unique-constraint purposes, so manual drills (NULL, NULL) can
    # coexist without violating this constraint — this is intentional.
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "scheduled_for_date",
            name="uq_recovery_drill_schedule_slot",
        ),
    )

    id = Column(Integer, primary_key=True)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    replay_run_id = Column(Integer, nullable=True, index=True)
    benchmark_profile_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, index=True)
    trigger_mode = Column(String, nullable=False, index=True, default="manual")
    schedule_id = Column(
        Integer,
        ForeignKey("recovery_drill_schedules.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    scheduled_for_date = Column(Date, nullable=True, index=True)
    latest_replayable_day = Column(Date, nullable=True)
    completed_trading_day_delta = Column(Integer, nullable=True)
    abort_reason = Column(Text, nullable=True)
    drill_started_at = Column(DateTime(timezone=True), nullable=False)
    drill_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class RecoveryDrillSchedule(Base):
    __tablename__ = "recovery_drill_schedules"

    id = Column(Integer, primary_key=True)
    market = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=True, index=True)
    cadence = Column(String, nullable=False)
    day_of_month = Column(Integer, nullable=False)
    timezone = Column(String, nullable=False, default="Asia/Taipei")
    benchmark_profile_id = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class BenchmarkProfile(Base):
    __tablename__ = "benchmark_profiles"

    id = Column(String, primary_key=True)
    cpu_class = Column(String, nullable=False)
    memory_size = Column(String, nullable=False)
    storage_type = Column(String, nullable=False)
    compression_settings = Column(String, nullable=False)
    archive_layout_version = Column(String, nullable=False)
    network_class = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class IngestionWatchlist(Base):
    __tablename__ = "ingestion_watchlist"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "market", name="uq_ingestion_watchlist_symbol_market"
        ),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    years = Column(Integer, nullable=False, default=5)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ScheduledIngestionRun(Base):
    __tablename__ = "scheduled_ingestion_runs"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id",
            "scheduled_for_date",
            name="uq_scheduled_ingestion_watchlist_slot",
        ),
    )

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(
        Integer,
        ForeignKey("ingestion_watchlist.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    scheduled_for_date = Column(Date, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error_message = Column(Text, nullable=True)
    first_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ScheduledIngestionAttempt(Base):
    __tablename__ = "scheduled_ingestion_attempts"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "attempt_number",
            name="uq_scheduled_ingestion_attempt_run_number",
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(
        Integer,
        ForeignKey("scheduled_ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
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


class TwCompanyProfile(Base):
    __tablename__ = "tw_company_profiles"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_tw_company_profiles_symbol_exchange",
        ),
    )

    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True, default="TW")
    exchange = Column(String, nullable=False, index=True)
    board = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    isin_code = Column(String, nullable=True)
    industry_category = Column(String, nullable=True, index=True)
    listing_date = Column(Date, nullable=True, index=True)
    trading_status = Column(String, nullable=False, index=True, default="active")
    source_name = Column(String, nullable=False)
    raw_payload_id = Column(Integer, nullable=True, index=True)
    archive_object_reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class TickArchiveRun(Base):
    __tablename__ = "tick_archive_runs"

    id = Column(Integer, primary_key=True)
    source_name = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    trigger_mode = Column(String, nullable=False, index=True)
    scope = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    symbol_count = Column(Integer, nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    observation_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    abort_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TickArchiveObject(Base):
    __tablename__ = "tick_archive_objects"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        Integer,
        ForeignKey("tick_archive_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_backend = Column(String, nullable=False)
    object_key = Column(String, nullable=False, unique=True)
    compression_codec = Column(String, nullable=False)
    archive_layout_version = Column(String, nullable=False)
    compressed_bytes = Column(Integer, nullable=False, default=0)
    uncompressed_bytes = Column(Integer, nullable=False, default=0)
    compression_ratio = Column(Float, nullable=False, default=0.0)
    record_count = Column(Integer, nullable=False, default=0)
    first_observation_ts = Column(DateTime(timezone=True), nullable=True)
    last_observation_ts = Column(DateTime(timezone=True), nullable=True)
    checksum = Column(String, nullable=False)
    retention_class = Column(String, nullable=False)
    backup_backend = Column(String, nullable=True)
    backup_object_key = Column(String, nullable=True)
    backup_status = Column(String, nullable=True, index=True)
    backup_completed_at = Column(DateTime(timezone=True), nullable=True)
    backup_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TickRestoreRun(Base):
    __tablename__ = "tick_restore_runs"

    id = Column(Integer, primary_key=True)
    archive_object_id = Column(
        Integer,
        ForeignKey("tick_archive_objects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    benchmark_profile_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    restore_status = Column(String, nullable=False, index=True)
    restored_row_count = Column(Integer, nullable=False, default=0)
    restore_started_at = Column(DateTime(timezone=True), nullable=False)
    restore_completed_at = Column(DateTime(timezone=True), nullable=True)
    elapsed_seconds = Column(Float, nullable=True)
    throughput_gb_per_minute = Column(Float, nullable=True)
    abort_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TickObservation(Base):
    __tablename__ = "tick_observations"
    __table_args__ = (
        UniqueConstraint(
            "archive_object_reference",
            "symbol",
            "observation_ts",
            name="uq_tick_observation_archive_symbol_ts",
        ),
        Index("idx_tick_observations_symbol_ts", "symbol", "observation_ts"),
    )

    id = Column(Integer, primary_key=True)
    trading_date = Column(Date, nullable=False, index=True)
    observation_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    last_price = Column(Float, nullable=True)
    last_size = Column(Integer, nullable=True)
    cumulative_volume = Column(Integer, nullable=True)
    best_bid_prices_json = Column(Text, nullable=False, default="[]")
    best_bid_sizes_json = Column(Text, nullable=False, default="[]")
    best_ask_prices_json = Column(Text, nullable=False, default="[]")
    best_ask_sizes_json = Column(Text, nullable=False, default="[]")
    source_name = Column(String, nullable=False)
    archive_object_reference = Column(String, nullable=False, index=True)
    parser_version = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExternalRawArchive(Base):
    __tablename__ = "external_raw_archives"

    id = Column(Integer, primary_key=True)
    source_family = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True, default="TW")
    coverage_start = Column(Date, nullable=False, index=True)
    coverage_end = Column(Date, nullable=False, index=True)
    record_count = Column(Integer, nullable=False, default=0)
    payload_body = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExternalSignalRecord(Base):
    __tablename__ = "external_signal_records"
    __table_args__ = (
        Index(
            "idx_external_signal_records_symbol_date",
            "symbol",
            "effective_date",
        ),
    )

    id = Column(Integer, primary_key=True)
    archive_id = Column(
        Integer,
        ForeignKey("external_raw_archives.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_family = Column(String, nullable=False, index=True)
    source_record_type = Column(String, nullable=False)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True, default="TW")
    effective_date = Column(Date, nullable=False, index=True)
    available_at = Column(DateTime(timezone=True), nullable=True, index=True)
    availability_mode = Column(String, nullable=False)
    lineage_version = Column(String, nullable=False)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExternalSignalAudit(Base):
    __tablename__ = "external_signal_audits"

    id = Column(Integer, primary_key=True)
    source_family = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True, default="TW")
    audit_window_start = Column(Date, nullable=False)
    audit_window_end = Column(Date, nullable=False)
    sample_size = Column(Integer, nullable=False, default=0)
    fallback_sample_size = Column(Integer, nullable=False, default=0)
    undocumented_count = Column(Integer, nullable=False, default=0)
    draw_rule_version = Column(String, nullable=False)
    result_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FactorCatalog(Base):
    __tablename__ = "factor_catalogs"

    id = Column(String, primary_key=True)
    market = Column(String, nullable=False, index=True, default="TW")
    source_family = Column(String, nullable=False)
    lineage_version = Column(String, nullable=False)
    minimum_coverage_ratio = Column(Float, nullable=False, default=0.8)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FactorCatalogEntry(Base):
    __tablename__ = "factor_catalog_entries"
    __table_args__ = (
        UniqueConstraint(
            "catalog_id",
            "factor_id",
            name="uq_factor_catalog_entries_catalog_factor",
        ),
    )

    id = Column(Integer, primary_key=True)
    catalog_id = Column(
        String,
        ForeignKey("factor_catalogs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    factor_id = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    formula_definition = Column(Text, nullable=False)
    lineage = Column(String, nullable=False)
    timing_semantics = Column(String, nullable=False)
    missing_value_policy = Column(String, nullable=False)
    scoring_eligible = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FactorMaterialization(Base):
    __tablename__ = "factor_materializations"
    __table_args__ = (
        Index(
            "idx_factor_materializations_run_symbol_date",
            "run_id",
            "symbol",
            "trading_date",
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    catalog_id = Column(
        String,
        ForeignKey("factor_catalogs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    factor_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True, default="TW")
    trading_date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=True)
    source_available_at = Column(DateTime(timezone=True), nullable=True)
    factor_available_ts = Column(DateTime(timezone=True), nullable=True)
    availability_mode = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class FactorUsabilityObservation(Base):
    __tablename__ = "factor_usability_observations"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    catalog_id = Column(
        String,
        ForeignKey("factor_catalogs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trading_date = Column(Date, nullable=False, index=True)
    factor_id = Column(String, nullable=False, index=True)
    coverage_ratio = Column(Float, nullable=False, default=0.0)
    materialization_latency_hours = Column(Float, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ClusterSnapshot(Base):
    __tablename__ = "cluster_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_version = Column(String, nullable=False, index=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    factor_catalog_version = Column(String, nullable=True)
    market = Column(String, nullable=False, index=True, default="TW")
    trading_date = Column(Date, nullable=False, index=True)
    cluster_count = Column(Integer, nullable=False, default=0)
    symbol_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ClusterMembership(Base):
    __tablename__ = "cluster_memberships"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "symbol",
            name="uq_cluster_membership_snapshot_symbol",
        ),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(
        Integer,
        ForeignKey("cluster_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol = Column(String, nullable=False, index=True)
    cluster_label = Column(String, nullable=False)
    distance_to_centroid = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PeerFeatureRun(Base):
    __tablename__ = "peer_feature_runs"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_id = Column(
        Integer,
        ForeignKey("cluster_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    peer_policy_version = Column(String, nullable=False)
    market = Column(String, nullable=False, index=True, default="TW")
    trading_date = Column(Date, nullable=False, index=True)
    status = Column(String, nullable=False)
    produced_feature_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    warning_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PeerComparisonOverlay(Base):
    __tablename__ = "peer_comparison_overlays"

    id = Column(Integer, primary_key=True)
    peer_feature_run_id = Column(
        Integer,
        ForeignKey("peer_feature_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol = Column(String, nullable=False, index=True)
    peer_symbol_count = Column(Integer, nullable=False, default=0)
    peer_feature_value = Column(Float, nullable=True)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SimulationProfile(Base):
    __tablename__ = "simulation_profiles"

    id = Column(String, primary_key=True)
    market = Column(String, nullable=False, index=True, default="TW")
    ack_latency_seconds = Column(Float, nullable=False, default=5.0)
    fill_latency_seconds = Column(Float, nullable=False, default=30.0)
    slippage_bps = Column(Float, nullable=False, default=5.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class LiveControlProfile(Base):
    __tablename__ = "live_control_profiles"

    id = Column(String, primary_key=True)
    market = Column(String, nullable=False, index=True, default="TW")
    live_control_version = Column(String, nullable=False)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionFailureTaxonomy(Base):
    __tablename__ = "execution_failure_taxonomies"

    code = Column(String, primary_key=True)
    route = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionOrder(Base):
    __tablename__ = "execution_orders"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    route = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    requested_price = Column(Float, nullable=True)
    status = Column(String, nullable=False, index=True)
    simulation_profile_id = Column(
        String,
        ForeignKey("simulation_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    live_control_profile_id = Column(
        String,
        ForeignKey("live_control_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    failure_code = Column(String, nullable=True, index=True)
    manual_confirmation = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionOrderEvent(Base):
    __tablename__ = "execution_order_events"

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False, index=True)
    event_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionFillEvent(Base):
    __tablename__ = "execution_fill_events"

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fill_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    fill_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    slippage_bps = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ExecutionPositionSnapshot(Base):
    __tablename__ = "execution_position_snapshots"

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("execution_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    route = Column(String, nullable=False, index=True)
    market = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    snapshot_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class LiveRiskCheck(Base):
    __tablename__ = "live_risk_checks"

    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String, nullable=False, index=True)
    detail_json = Column(Text, nullable=False, default="{}")
    checked_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class KillSwitchEvent(Base):
    __tablename__ = "kill_switch_events"

    id = Column(Integer, primary_key=True)
    scope_type = Column(String, nullable=False, index=True)
    market = Column(String, nullable=True, index=True)
    is_enabled = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdaptiveProfile(Base):
    __tablename__ = "adaptive_profiles"

    id = Column(String, primary_key=True)
    market = Column(String, nullable=False, index=True, default="TW")
    reward_definition_version = Column(String, nullable=False)
    state_definition_version = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdaptiveRolloutControl(Base):
    __tablename__ = "adaptive_rollout_controls"

    id = Column(String, primary_key=True)
    profile_id = Column(
        String,
        ForeignKey("adaptive_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rollout_control_version = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    detail_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdaptiveTrainingRun(Base):
    __tablename__ = "adaptive_training_runs"

    id = Column(Integer, primary_key=True)
    profile_id = Column(
        String,
        ForeignKey("adaptive_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    market = Column(String, nullable=False, index=True, default="TW")
    adaptive_mode = Column(String, nullable=False, index=True)
    reward_definition_version = Column(String, nullable=False)
    state_definition_version = Column(String, nullable=False)
    rollout_control_version = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    dataset_summary_json = Column(Text, nullable=False, default="{}")
    artifact_registry_json = Column(Text, nullable=False, default="{}")
    validation_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AdaptiveSurfaceExclusion(Base):
    __tablename__ = "adaptive_surface_exclusions"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        String,
        ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    exclusion_surface = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
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
