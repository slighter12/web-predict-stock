from __future__ import annotations

from copy import deepcopy
from typing import Any

CALIBRATION_POLICY_VERSION = "pooled_calibration_matrix_v3"
CALIBRATION_FOLD_POLICY_VERSION = (
    "expanding_three_market_date_folds_target_end_purged_v2"
)
CALIBRATION_RESOURCE_POLICY_VERSION = "process_wall_cpu_rss_model_fit_breakdown_v2"
CALIBRATION_CAPACITY_PRESET_VERSION = "calibration_tree_capacity_v1"
CALIBRATION_REQUEST_BOUNDS_POLICY_VERSION = "calibration_request_bounds_v1"
CALIBRATION_DATA_SOURCE_POLICY_VERSION = (
    "tw_official_preferred_yfinance_fallback_v1"
)
CALIBRATION_FEATURE_CONTINUITY_POLICY_VERSION = (
    "observed-row-features_global-market-date-target-boundaries_v1"
)
CALIBRATION_MARKET_DATE_AXIS_POLICY_VERSION = (
    "tw_official_market_lane_excluding_confirmed_no_data_v2"
)
CALIBRATION_MAX_SYMBOLS = 200
CALIBRATION_MAX_FEATURES = 12
CALIBRATION_MAX_DATE_COUNT = 1_827
CALIBRATION_FOLD_COUNT = 3
CALIBRATION_TEST_SIZE = 0.2
CALIBRATION_EXECUTED_PRESET = "balanced"
CALIBRATION_CANDIDATE_GRID_POLICY_VERSION = "tw_open_to_open_direction_gate_grid_v1"
CALIBRATION_DIRECTION_GATE_POLICY_VERSION = (
    "pooled_market_date_tail_20pct_min20_class5_probability_0p5_v2"
)
CALIBRATION_VOLATILITY_POLICY_VERSION = (
    "open_to_open_signal_date_sample_std_ddof1_full_window_v1"
)
CALIBRATION_MATCHED_BASELINE_POLICY_VERSION = (
    "matched_ungated_score_top_n_on_action_dates_v2"
)
CALIBRATION_REFERENCE_BASELINE_POLICY_VERSION = (
    "eligible_date_ungated_score_top_n_reference_v1"
)
CALIBRATION_HORIZON_OUTCOME_POLICY_VERSION = (
    "open_to_open_target_entry_exit_net_return_v1"
)
CALIBRATION_VOLATILITY_LOOKBACKS = (20, 60, 252)
CALIBRATION_VOLATILITY_MULTIPLIERS = (0.5, 0.75, 1.0)
CALIBRATION_TOP_N_VALUES = (5, 10, 20)
CALIBRATION_DIRECTION_PROBABILITY_CUTOFF = 0.5
CALIBRATION_DIRECTION_CALIBRATION_TAIL_FRACTION = 0.2
CALIBRATION_DIRECTION_CALIBRATION_MIN_SAMPLES = 20
CALIBRATION_DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT = 5
CALIBRATION_FEE = 0.002
CALIBRATION_SLIPPAGE = 0.001

SUPPORTED_CALIBRATION_MODEL_FAMILIES = (
    "extra_trees",
    "random_forest",
    "xgboost",
)
CALIBRATION_CAPACITY_PRESET_NAMES = (
    "conservative",
    "balanced",
    "flexible",
)

# Keep the existing official source ordering as the canonical tie-breaker.
# ``official`` remains a compatibility alias for deterministic test fixtures.
CALIBRATION_SOURCE_PRIORITY = {
    "twse": 0,
    "official": 0,
    "twse_mi_index": 1,
    "tpex_aftertrading_otc": 2,
    "yfinance": 3,
}

_SKLEARN_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "n_estimators": 50,
        "max_depth": 6,
        "min_samples_split": 10,
        "min_samples_leaf": 4,
        "n_jobs": -1,
        "random_state": 42,
    },
    "balanced": {
        "n_estimators": 200,
        "max_depth": 12,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "n_jobs": -1,
        "random_state": 42,
    },
    "flexible": {
        "n_estimators": 400,
        "max_depth": 16,
        "min_samples_split": 2,
        "min_samples_leaf": 1,
        "n_jobs": -1,
        "random_state": 42,
    },
}

_XGBOOST_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "n_estimators": 50,
        "max_depth": 3,
        "min_child_weight": 5,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "n_jobs": -1,
        "random_state": 42,
    },
    "balanced": {
        "n_estimators": 200,
        "max_depth": 6,
        "min_child_weight": 1,
        "learning_rate": 0.1,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "n_jobs": -1,
        "random_state": 42,
    },
    "flexible": {
        "n_estimators": 400,
        "max_depth": 8,
        "min_child_weight": 1,
        "learning_rate": 0.05,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "n_jobs": -1,
        "random_state": 42,
    },
}


def capacity_presets_for(model_type: str) -> dict[str, dict[str, Any]]:
    if model_type not in SUPPORTED_CALIBRATION_MODEL_FAMILIES:
        raise ValueError(f"Unsupported calibration model family: {model_type}")
    presets = _XGBOOST_PRESETS if model_type == "xgboost" else _SKLEARN_PRESETS
    return deepcopy(presets)
