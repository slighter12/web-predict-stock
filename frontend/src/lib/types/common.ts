export type MarketCode = "TW" | "US";
export type PriceSource = "open" | "high" | "low" | "close" | "volume";
export type FeatureName = "ma" | "rsi";
export type ReturnTarget = "open_to_open" | "close_to_close" | "open_to_close";
export type ValidationMethod =
  | "holdout"
  | "walk_forward"
  | "rolling_window"
  | "expanding_window";
export type BaselineName = "buy_and_hold" | "naive_momentum" | "ma_crossover";
export type RuntimeMode = "runtime_compatibility_mode" | "vnext_spec_mode";
export type DefaultBundleVersion = "research_spec_v1";
export type ConfigValueSource = "request_override" | "spec_default";
export type FallbackOutcome = "not_needed" | "accepted" | "rejected";
export type ComparisonEligibility =
  | "comparison_metadata_only"
  | "sample_window_pending"
  | "strategy_pair_comparable"
  | "research_only_comparable"
  | "unresolved_event_quarantine";
export type RunStatus =
  | "succeeded"
  | "rejected"
  | "validation_failed"
  | "failed";
export type RecoveryDrillTriggerMode = "manual" | "scheduled";
export type RecoveryDrillCadence = "monthly";
export type LifecycleEventType =
  | "listing"
  | "delisting"
  | "ticker_change"
  | "re_listing";
export type ImportantEventType =
  | "listing_status_change"
  | "delisting"
  | "ticker_change"
  | "stock_split"
  | "reverse_split"
  | "cash_dividend"
  | "stock_dividend"
  | "capital_reduction"
  | "merger"
  | "tender_offer";
export type TimestampSourceClass =
  | "official_exchange"
  | "official_issuer"
  | "vendor_published";
export type VersionFieldStatus = "implemented" | "placeholder";
