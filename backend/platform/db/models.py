from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import Column, Text

from .session import mapper_registry


class AdaptiveProfile:
    pass


class AdaptiveRolloutControl:
    pass


class AdaptiveSurfaceExclusion:
    pass


class AdaptiveTrainingRun:
    pass


class BenchmarkProfile:
    pass


class ClusterMembership:
    pass


class ClusterSnapshot:
    pass


class DailyOHLCV:
    pass


class ExecutionFailureTaxonomy:
    pass


class ExecutionFillEvent:
    pass


class ExecutionOrder:
    pass


class ExecutionOrderEvent:
    pass


class ExecutionPositionSnapshot:
    pass


class ExternalRawArchive:
    pass


class ExternalSignalAudit:
    pass


class ExternalSignalRecord:
    pass


class FactorCatalog:
    pass


class FactorCatalogEntry:
    pass


class FactorMaterialization:
    pass


class FactorUsabilityObservation:
    pass


class ImportantEvent:
    pass


class IngestionWatchlist:
    pass


class KillSwitchEvent:
    pass


class LiveControlProfile:
    pass


class LiveRiskCheck:
    pass


class MicrostructureObservation:
    pass


class MinuteOHLCV:
    pass


class NormalizedReplayRun:
    pass


class PeerComparisonOverlay:
    pass


class PeerFeatureRun:
    pass


class RawIngestAudit:
    pass


class RecoveryDrill:
    pass


class RecoveryDrillSchedule:
    pass


class ResearchRun:
    pass


class ResearchRunLiquidityCoverage:
    pass


class ScheduledIngestionAttempt:
    pass


class ScheduledIngestionRun:
    pass


class SimulationProfile:
    pass


class SymbolLifecycleRecord:
    pass


class TickArchiveObject:
    pass


class TickArchiveRun:
    pass


class TickObservation:
    pass


class TickRestoreRun:
    pass


class TwCompanyProfile:
    pass


_MODEL_TABLES = {
    "adaptive_profiles": AdaptiveProfile,
    "adaptive_rollout_controls": AdaptiveRolloutControl,
    "adaptive_surface_exclusions": AdaptiveSurfaceExclusion,
    "adaptive_training_runs": AdaptiveTrainingRun,
    "benchmark_profiles": BenchmarkProfile,
    "cluster_memberships": ClusterMembership,
    "cluster_snapshots": ClusterSnapshot,
    "daily_ohlcv": DailyOHLCV,
    "execution_failure_taxonomies": ExecutionFailureTaxonomy,
    "execution_fill_events": ExecutionFillEvent,
    "execution_orders": ExecutionOrder,
    "execution_order_events": ExecutionOrderEvent,
    "execution_position_snapshots": ExecutionPositionSnapshot,
    "external_raw_archives": ExternalRawArchive,
    "external_signal_audits": ExternalSignalAudit,
    "external_signal_records": ExternalSignalRecord,
    "factor_catalogs": FactorCatalog,
    "factor_catalog_entries": FactorCatalogEntry,
    "factor_materializations": FactorMaterialization,
    "factor_usability_observations": FactorUsabilityObservation,
    "important_events": ImportantEvent,
    "ingestion_watchlist": IngestionWatchlist,
    "kill_switch_events": KillSwitchEvent,
    "live_control_profiles": LiveControlProfile,
    "live_risk_checks": LiveRiskCheck,
    "microstructure_observations": MicrostructureObservation,
    "minute_ohlcv": MinuteOHLCV,
    "normalized_replay_runs": NormalizedReplayRun,
    "peer_comparison_overlays": PeerComparisonOverlay,
    "peer_feature_runs": PeerFeatureRun,
    "raw_ingest_audit": RawIngestAudit,
    "recovery_drills": RecoveryDrill,
    "recovery_drill_schedules": RecoveryDrillSchedule,
    "research_runs": ResearchRun,
    "research_run_liquidity_coverages": ResearchRunLiquidityCoverage,
    "scheduled_ingestion_attempts": ScheduledIngestionAttempt,
    "scheduled_ingestion_runs": ScheduledIngestionRun,
    "simulation_profiles": SimulationProfile,
    "symbol_lifecycle_records": SymbolLifecycleRecord,
    "tick_archive_objects": TickArchiveObject,
    "tick_archive_runs": TickArchiveRun,
    "tick_observations": TickObservation,
    "tick_restore_runs": TickRestoreRun,
    "tw_company_profiles": TwCompanyProfile,
}

_MIGRATION_FILES = [
    "0001_core_platform.py",
    "0002_market_ops.py",
    "0003_tick_archive.py",
    "0004_research_foundations.py",
    "0005_execution.py",
    "0006_adaptive.py",
    "0007_minute_ohlcv.py",
]


def _load_migration_module(filename: str):
    migrations_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    path = migrations_dir / filename
    spec = importlib.util.spec_from_file_location(f"_schema_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load migration schema from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_tables() -> None:
    for filename in _MIGRATION_FILES:
        module = _load_migration_module(filename)
        for table in module.metadata.sorted_tables:
            if table.name in mapper_registry.metadata.tables:
                continue
            table.to_metadata(mapper_registry.metadata)

    research_runs = mapper_registry.metadata.tables["research_runs"]
    for column_name in (
        "equity_curve_json",
        "signals_json",
        "model_diagnostics_json",
        "baselines_json",
    ):
        if column_name not in research_runs.c:
            research_runs.append_column(Column(column_name, Text(), nullable=True))


def _map_models() -> None:
    for table_name, model_class in _MODEL_TABLES.items():
        mapper_registry.map_imperatively(
            model_class, mapper_registry.metadata.tables[table_name]
        )


_load_tables()
_map_models()

__all__ = [model.__name__ for model in _MODEL_TABLES.values()]
