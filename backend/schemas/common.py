from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

MarketCode = Literal["TW", "US"]
PriceSource = Literal["open", "high", "low", "close", "volume"]
FeatureName = Literal["ma", "rsi"]
ReturnTarget = Literal["open_to_open", "close_to_close", "open_to_close"]
ModelType = Literal["xgboost"]
StrategyType = Literal["research_v1"]
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
RunStatus = Literal["succeeded", "rejected", "validation_failed", "failed"]
ReplayStatus = Literal["succeeded", "failed"]
RecoveryDrillStatus = Literal["succeeded", "failed"]
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


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
