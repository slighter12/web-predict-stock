from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

MarketCode = Literal["TW", "US"]
PriceSource = Literal["open", "high", "low", "close", "volume"]
FeatureName = Literal["ma", "rsi"]
ReturnTarget = Literal["open_to_open", "close_to_close", "open_to_close"]
ModelType = Literal["xgboost", "random_forest", "extra_trees"]
StrategyType = Literal["research_v1"]
ExecutionRoute = Literal["research_only", "simulation_internal_v1", "live_stub_v1"]
AdaptiveMode = Literal["off", "shadow", "candidate"]
ExternalAvailabilityMode = Literal["exact", "fallback", "unresolved"]
ValidationMethod = Literal[
    "holdout", "walk_forward", "rolling_window", "expanding_window"
]
BaselineName = Literal["buy_and_hold", "naive_momentum", "ma_crossover"]
RuntimeMode = Literal["runtime_compatibility_mode", "vnext_spec_mode"]
DefaultBundleVersion = Literal["research_spec_v1"]
ConfigValueSource = Literal["request_override", "spec_default"]
FallbackOutcome = Literal["not_needed", "accepted", "rejected"]
ComparisonEligibility = Literal[
    "comparison_metadata_only",
    "sample_window_pending",
    "strategy_pair_comparable",
    "research_only_comparable",
    "unresolved_event_quarantine",
]
TradabilityState = Literal[
    "execution_ready",
    "research_only",
    "unresolved_corporate_event",
    "stale_risk",
]
MissingFeaturePolicyState = Literal[
    "feature_complete",
    "core_data_gaps_filtered",
    "native_missing_supported",
]
CorporateEventState = Literal["clear", "unresolved_corporate_event"]
MonitorObservationStatus = Literal["not_requested", "persisted", "skipped"]
ResearchMonitorProfileId = Literal["p3_monitor_default_v1"]
TradabilityContractVersion = Literal["p3_tradability_monitoring_v1"]
RunStatus = Literal["running", "succeeded", "rejected", "validation_failed", "failed"]
ReplayStatus = Literal["succeeded", "failed"]
RecoveryDrillStatus = Literal["succeeded", "failed"]
RecoveryDrillTriggerMode = Literal["manual", "scheduled"]
RecoveryDrillCadence = Literal["monthly"]
ScheduledIngestionStatus = Literal["succeeded", "failed"]
TickArchiveStatus = Literal["succeeded", "failed"]
TickArchiveTriggerMode = Literal["post_close_crawl", "manual_import"]
TickStorageBackend = Literal["local_filesystem"]
TickCompressionCodec = Literal["gzip"]
ArchiveBackupBackend = Literal["google_drive_mirror"]
ArchiveBackupStatus = Literal["not_configured", "succeeded", "failed"]
ExecutionOrderSide = Literal["buy", "sell"]
ExecutionOrderStatus = Literal[
    "submitted",
    "acknowledged",
    "filled",
    "rejected",
    "accepted_for_stub_dispatch",
]
ExecutionOrderEventType = Literal[
    "submitted",
    "acknowledged",
    "filled",
    "rejected",
    "position_readback",
]
RiskCheckStatus = Literal["pass", "fail"]
KillSwitchScope = Literal["global", "market"]
AdaptiveTrainingStatus = Literal["queued", "validated", "failed"]
KpiStatus = Literal["pass", "fail", "insufficient_sample"]
LifecycleEventType = Literal["listing", "delisting", "ticker_change", "re_listing"]
ImportantEventType = Literal[
    "listing_status_change",
    "delisting",
    "ticker_change",
    "stock_split",
    "reverse_split",
    "cash_dividend",
    "stock_dividend",
    "capital_reduction",
    "merger",
    "tender_offer",
]
TimestampSourceClass = Literal[
    "official_exchange", "official_issuer", "vendor_published"
]
VersionFieldStatus = Literal["implemented", "placeholder"]
ACTIVE_TRADABILITY_CONTRACT_VERSION = "p3_tradability_monitoring_v1"


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
