from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import distinct, select

from ..database import DailyOHLCV, ImportantEvent, SessionLocal, SymbolLifecycleRecord
from ..errors import DataAccessError
from ..schemas.common import ACTIVE_TRADABILITY_CONTRACT_VERSION
from ..schemas.research_runs import ResearchRunCreateRequest
from ..strategy_service import ResearchStrategyConfig

MIN_EXECUTION_HISTORY_DAYS = 120
RECENT_COMPLETENESS_WINDOW = 20
RECENT_COMPLETENESS_THRESHOLD = 0.95
CAPACITY_LIMIT_RATIO = 0.005
MONITOR_PROFILE_ID = "p3_monitor_default_v1"
LIQUIDITY_BUCKET_SCHEMA_VERSION = "liquidity_adv20_twd_bands_v1"
ADV_BASIS_VERSION = "raw_close_x_volume_active_session_v1"
CAPACITY_SCREENING_VERSION = "adv_ex_ante_buy_notional_0p5pct_v1"
MISSING_FEATURE_POLICY_VERSION = "xgboost_native_missing_v1"
EXECUTION_COST_MODEL_VERSION = "fees_slippage_only_v1"

_BLOCKING_UNRESOLVED_EVENT_TYPES = {"merger", "tender_offer"}
_NON_BLOCKING_EXPLICIT_EVENT_TYPES = {
    "stock_split",
    "reverse_split",
    "cash_dividend",
    "stock_dividend",
    "capital_reduction",
}
_ACTIVE_LIFECYCLE_EVENT_TYPES = {"listing", "re_listing"}
_TERMINAL_LIFECYCLE_EVENT_TYPES = {"delisting"}
_CORE_FIELDS = ("open", "high", "low", "close", "volume")
_LIQUIDITY_BUCKETS: list[tuple[float, str, str]] = [
    (10_000_000.0, "lt_10m", "< 10M TWD"),
    (50_000_000.0, "10m_to_50m", "10M-50M TWD"),
    (200_000_000.0, "50m_to_200m", "50M-200M TWD"),
    (float("inf"), "ge_200m", ">= 200M TWD"),
]


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    normalized = frame.copy()
    normalized.index = pd.to_datetime(normalized.index)
    normalized = normalized.sort_index()
    return normalized


def _load_symbol_frames(
    symbols: list[str],
    market: str,
    end_date: date,
) -> dict[str, pd.DataFrame]:
    if not symbols:
        return {}

    try:
        with SessionLocal() as session:
            stmt = (
                select(DailyOHLCV)
                .where(DailyOHLCV.market == market)
                .where(DailyOHLCV.symbol.in_(symbols))
                .where(DailyOHLCV.date <= end_date)
                .order_by(DailyOHLCV.date.asc())
            )
            rows = session.execute(stmt).scalars().all()
    except Exception as exc:
        raise DataAccessError("Failed to load P3 market data.") from exc

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(
            {
                "date": row.date,
                "symbol": row.symbol,
                "market": row.market,
                "source": row.source,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
        )

    return {
        symbol: _normalize_frame(pd.DataFrame(grouped[symbol]).set_index("date"))
        if grouped[symbol]
        else pd.DataFrame()
        for symbol in symbols
    }


def _load_market_trading_dates(market: str, end_date: date) -> list[date]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(distinct(DailyOHLCV.date))
                .where(DailyOHLCV.market == market)
                .where(DailyOHLCV.date <= end_date)
                .order_by(DailyOHLCV.date.asc())
            )
            return [item[0] for item in session.execute(stmt).all()]
    except Exception as exc:
        raise DataAccessError("Failed to load P3 trading dates.") from exc


def _load_lifecycle_events(
    symbols: list[str],
    market: str,
    end_date: date,
) -> dict[str, list[SymbolLifecycleRecord]]:
    grouped: dict[str, list[SymbolLifecycleRecord]] = defaultdict(list)
    loaded_symbols: set[str] = set()
    pending = {symbol for symbol in symbols if symbol}

    try:
        with SessionLocal() as session:
            while pending:
                batch = sorted(pending - loaded_symbols)
                if not batch:
                    break
                stmt = (
                    select(SymbolLifecycleRecord)
                    .where(SymbolLifecycleRecord.market == market)
                    .where(SymbolLifecycleRecord.symbol.in_(batch))
                    .where(SymbolLifecycleRecord.effective_date <= end_date)
                    .order_by(
                        SymbolLifecycleRecord.symbol.asc(),
                        SymbolLifecycleRecord.effective_date.asc(),
                        SymbolLifecycleRecord.id.asc(),
                    )
                )
                rows = session.execute(stmt).scalars().all()
                loaded_symbols.update(batch)
                for row in rows:
                    grouped[row.symbol].append(row)
                    if row.event_type == "ticker_change" and row.reference_symbol:
                        pending.add(row.reference_symbol.strip())
    except Exception as exc:
        raise DataAccessError("Failed to load lifecycle events.") from exc

    return grouped


def _load_important_events(
    symbols: list[str],
    market: str,
    end_date: date,
) -> dict[str, list[ImportantEvent]]:
    if not symbols:
        return {}
    try:
        with SessionLocal() as session:
            stmt = (
                select(ImportantEvent)
                .where(ImportantEvent.market == market)
                .where(ImportantEvent.symbol.in_(symbols))
                .order_by(
                    ImportantEvent.symbol.asc(),
                    ImportantEvent.event_publication_ts.asc(),
                    ImportantEvent.id.asc(),
                )
            )
            rows = session.execute(stmt).scalars().all()
    except Exception as exc:
        raise DataAccessError("Failed to load important events.") from exc

    grouped: dict[str, list[ImportantEvent]] = defaultdict(list)
    for row in rows:
        if row.event_publication_ts.date() <= end_date:
            grouped[row.symbol].append(row)
    return grouped


def _window_dates(
    market_trading_dates: list[date],
    as_of_date: date,
    window: int,
) -> list[date]:
    index = bisect_right(market_trading_dates, as_of_date)
    start = max(0, index - window)
    return market_trading_dates[start:index]


def _row_is_complete(frame: pd.DataFrame, trading_date: date) -> bool:
    ts = pd.Timestamp(trading_date)
    if frame.empty or ts not in frame.index:
        return False
    row = frame.loc[ts]
    return all(pd.notna(row.get(field)) for field in _CORE_FIELDS)


def _history_count(frame: pd.DataFrame, as_of_date: date) -> int:
    if frame.empty:
        return 0
    rows = frame.loc[frame.index <= pd.Timestamp(as_of_date)]
    if rows.empty:
        return 0
    return int(rows.loc[:, _CORE_FIELDS].notna().all(axis=1).sum())


def _completeness_ratio(frame: pd.DataFrame, recent_dates: list[date]) -> float:
    if not recent_dates:
        return 0.0
    complete_days = sum(
        1 for trading_date in recent_dates if _row_is_complete(frame, trading_date)
    )
    return float(complete_days / len(recent_dates))


def _adv20(frame: pd.DataFrame, recent_dates: list[date]) -> float:
    values: list[float] = []
    for trading_date in recent_dates:
        ts = pd.Timestamp(trading_date)
        if frame.empty or ts not in frame.index:
            continue
        row = frame.loc[ts]
        if pd.isna(row.get("close")) or pd.isna(row.get("volume")):
            continue
        values.append(float(row["close"]) * float(row["volume"]))
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _liquidity_bucket(adv20: float) -> tuple[str, str]:
    for upper, bucket_key, bucket_label in _LIQUIDITY_BUCKETS:
        if adv20 < upper:
            return bucket_key, bucket_label
    return _LIQUIDITY_BUCKETS[-1][1], _LIQUIDITY_BUCKETS[-1][2]


def _event_effective_date(event: ImportantEvent) -> date:
    return event.effective_date or event.event_publication_ts.date()


def _latest_lifecycle_event(
    events: list[SymbolLifecycleRecord], as_of_date: date
) -> SymbolLifecycleRecord | None:
    latest = None
    for event in events:
        if event.effective_date <= as_of_date:
            latest = event
        else:
            break
    return latest


def _matching_lifecycle_event(
    events: list[SymbolLifecycleRecord],
    *,
    as_of_date: date,
    since_date: date,
    allowed_types: set[str],
) -> SymbolLifecycleRecord | None:
    for event in reversed(events):
        if event.effective_date > as_of_date:
            continue
        if event.effective_date < since_date:
            break
        if event.event_type in allowed_types:
            return event
    return None


def _resolve_symbol_identity(
    symbol: str,
    lifecycle_events_by_symbol: dict[str, list[SymbolLifecycleRecord]],
    *,
    as_of_date: date,
) -> dict[str, Any]:
    current_symbol = symbol
    visited: set[str] = set()
    symbol_path: list[str] = []

    while True:
        if current_symbol in visited:
            symbol_path.append(current_symbol)
            return {
                "resolved_symbol": current_symbol,
                "symbol_path": symbol_path,
                "lifecycle_active": False,
                "unresolved": True,
            }

        visited.add(current_symbol)
        symbol_path.append(current_symbol)
        latest = _latest_lifecycle_event(
            lifecycle_events_by_symbol.get(current_symbol, []),
            as_of_date,
        )
        if latest is None:
            return {
                "resolved_symbol": current_symbol,
                "symbol_path": symbol_path,
                "lifecycle_active": True,
                "unresolved": False,
            }
        if latest.event_type in _ACTIVE_LIFECYCLE_EVENT_TYPES:
            return {
                "resolved_symbol": current_symbol,
                "symbol_path": symbol_path,
                "lifecycle_active": True,
                "unresolved": False,
            }
        if latest.event_type in _TERMINAL_LIFECYCLE_EVENT_TYPES:
            return {
                "resolved_symbol": current_symbol,
                "symbol_path": symbol_path,
                "lifecycle_active": False,
                "unresolved": False,
            }
        if latest.event_type == "ticker_change":
            successor_symbol = (latest.reference_symbol or "").strip()
            if not successor_symbol:
                return {
                    "resolved_symbol": current_symbol,
                    "symbol_path": symbol_path,
                    "lifecycle_active": False,
                    "unresolved": True,
                }
            current_symbol = successor_symbol
            continue
        return {
            "resolved_symbol": current_symbol,
            "symbol_path": symbol_path,
            "lifecycle_active": True,
            "unresolved": False,
        }


def _corporate_event_clear(
    identity_state: dict[str, Any],
    important_events_by_symbol: dict[str, list[ImportantEvent]],
    lifecycle_events_by_symbol: dict[str, list[SymbolLifecycleRecord]],
    *,
    as_of_date: date,
) -> bool:
    if identity_state["unresolved"]:
        return False

    for symbol in identity_state["symbol_path"]:
        lifecycle_events = lifecycle_events_by_symbol.get(symbol, [])
        for event in important_events_by_symbol.get(symbol, []):
            effective_date = _event_effective_date(event)
            if effective_date > as_of_date:
                continue

            if event.event_type in _BLOCKING_UNRESOLVED_EVENT_TYPES:
                return False
            if event.event_type in _NON_BLOCKING_EXPLICIT_EVENT_TYPES:
                continue
            if event.event_type == "delisting":
                if (
                    _matching_lifecycle_event(
                        lifecycle_events,
                        as_of_date=as_of_date,
                        since_date=effective_date,
                        allowed_types={"delisting"},
                    )
                    is None
                ):
                    return False
                continue
            if event.event_type == "listing_status_change":
                if (
                    _matching_lifecycle_event(
                        lifecycle_events,
                        as_of_date=as_of_date,
                        since_date=effective_date,
                        allowed_types=_ACTIVE_LIFECYCLE_EVENT_TYPES
                        | _TERMINAL_LIFECYCLE_EVENT_TYPES,
                    )
                    is None
                ):
                    return False
                continue
            if event.event_type == "ticker_change":
                ticker_change_event = _matching_lifecycle_event(
                    lifecycle_events,
                    as_of_date=as_of_date,
                    since_date=effective_date,
                    allowed_types={"ticker_change"},
                )
                if (
                    ticker_change_event is None
                    or not (ticker_change_event.reference_symbol or "").strip()
                ):
                    return False
                continue
            return False

    return True


def _build_bucket_coverages(
    full_counts: dict[str, int],
    execution_counts: dict[str, int],
    full_universe_count: int,
) -> list[dict[str, Any]]:
    bucket_labels = {
        bucket_key: bucket_label for _, bucket_key, bucket_label in _LIQUIDITY_BUCKETS
    }
    coverages: list[dict[str, Any]] = []
    for _, bucket_key, _ in _LIQUIDITY_BUCKETS:
        full_count = int(full_counts.get(bucket_key, 0))
        execution_count = int(execution_counts.get(bucket_key, 0))
        coverages.append(
            {
                "bucket_key": bucket_key,
                "bucket_label": bucket_labels[bucket_key],
                "full_universe_count": full_count,
                "execution_universe_count": execution_count,
                "full_universe_ratio": (
                    float(full_count / full_universe_count)
                    if full_universe_count > 0
                    else 0.0
                ),
                "execution_coverage_ratio": (
                    float(execution_count / full_count) if full_count > 0 else 0.0
                ),
            }
        )
    return coverages


def build_p3_summary(
    *,
    request: ResearchRunCreateRequest,
    strategy: ResearchStrategyConfig,
    weights: pd.DataFrame,
    volume_df: pd.DataFrame,
) -> dict[str, Any]:
    trading_dates = [
        ts.date() for ts in pd.to_datetime(weights.index).sort_values().unique()
    ]
    if not trading_dates:
        return {
            "tradability_state": "research_only",
            "tradability_contract_version": ACTIVE_TRADABILITY_CONTRACT_VERSION,
            "capacity_screening_active": request.portfolio_aum is not None,
            "missing_feature_policy_state": "native_missing_supported",
            "corporate_event_state": "clear",
            "full_universe_count": len(request.symbols),
            "execution_universe_count": 0,
            "execution_universe_ratio": 0.0,
            "liquidity_bucket_schema_version": LIQUIDITY_BUCKET_SCHEMA_VERSION,
            "liquidity_bucket_coverages": [],
            "stale_mark_days_with_open_positions": 0,
            "stale_risk_share": 0.0,
            "monitor_observation_status": (
                "skipped"
                if request.monitor_profile_id == MONITOR_PROFILE_ID
                else "not_requested"
            ),
            "monitor_profile_id": request.monitor_profile_id,
            "microstructure_observations": [],
            "adv_basis_version": ADV_BASIS_VERSION,
            # The contract version remains declared even when screening is inactive.
            "capacity_screening_version": CAPACITY_SCREENING_VERSION,
            "missing_feature_policy_version": MISSING_FEATURE_POLICY_VERSION,
            "execution_cost_model_version": EXECUTION_COST_MODEL_VERSION,
            # P3 intentionally does not make investability claims until TBD-001 closes.
            "investability_screening_active": False,
        }

    full_universe_count = len(request.symbols)
    market_dates = _load_market_trading_dates(request.market, trading_dates[-1])
    lifecycle_events = _load_lifecycle_events(
        request.symbols, request.market, trading_dates[-1]
    )
    expanded_symbols = sorted(
        {
            *request.symbols,
            *lifecycle_events.keys(),
            *[
                (event.reference_symbol or "").strip()
                for events in lifecycle_events.values()
                for event in events
                if event.reference_symbol
            ],
        }
    )
    symbol_frames = _load_symbol_frames(
        expanded_symbols, request.market, trading_dates[-1]
    )
    important_events = _load_important_events(
        expanded_symbols, request.market, trading_dates[-1]
    )
    capacity_screening_active = request.portfolio_aum is not None
    max_name_buy_notional = (
        float(request.portfolio_aum) / float(strategy.top_n)
        if capacity_screening_active
        and strategy.top_n > 0
        and request.portfolio_aum is not None
        else None
    )

    daily_observations: list[dict[str, Any]] = []
    latest_missing_core_gap = False
    latest_corporate_event_clear = True
    latest_execution_universe_count = 0
    latest_bucket_coverages: list[dict[str, Any]] = []

    for trading_date in trading_dates:
        full_bucket_counts: dict[str, int] = defaultdict(int)
        execution_bucket_counts: dict[str, int] = defaultdict(int)
        execution_universe_count = 0
        any_missing_core_gap = False
        any_unresolved_event = False

        recent_dates = _window_dates(
            market_dates, trading_date, RECENT_COMPLETENESS_WINDOW
        )
        for symbol in request.symbols:
            identity_state = _resolve_symbol_identity(
                symbol,
                lifecycle_events,
                as_of_date=trading_date,
            )
            resolved_symbol = identity_state["resolved_symbol"]
            frame = symbol_frames.get(resolved_symbol)
            if frame is None:
                frame = symbol_frames.get(symbol, pd.DataFrame())
            history_ready = (
                _history_count(frame, trading_date) >= MIN_EXECUTION_HISTORY_DAYS
            )
            completeness_ratio = _completeness_ratio(frame, recent_dates)
            completeness_ready = completeness_ratio >= RECENT_COMPLETENESS_THRESHOLD
            lifecycle_active = bool(identity_state["lifecycle_active"])
            event_clear = _corporate_event_clear(
                identity_state,
                important_events,
                lifecycle_events,
                as_of_date=trading_date,
            )
            adv20 = _adv20(frame, recent_dates)
            bucket_key, _bucket_label = _liquidity_bucket(adv20)
            full_bucket_counts[bucket_key] += 1

            if not history_ready or not completeness_ready:
                any_missing_core_gap = True
            if not event_clear:
                any_unresolved_event = True

            capacity_pass = True
            if capacity_screening_active and max_name_buy_notional is not None:
                capacity_pass = (
                    adv20 > 0 and max_name_buy_notional <= adv20 * CAPACITY_LIMIT_RATIO
                )

            execution_eligible = (
                lifecycle_active
                and history_ready
                and completeness_ready
                and event_clear
                and capacity_pass
            )
            if execution_eligible:
                execution_universe_count += 1
                execution_bucket_counts[bucket_key] += 1

        bucket_coverages = _build_bucket_coverages(
            full_bucket_counts,
            execution_bucket_counts,
            full_universe_count,
        )
        daily_observations.append(
            {
                "trading_date": trading_date,
                "full_universe_count": full_universe_count,
                "execution_universe_count": execution_universe_count,
                "execution_universe_ratio": (
                    float(execution_universe_count / full_universe_count)
                    if full_universe_count > 0
                    else 0.0
                ),
                "bucket_coverages": bucket_coverages,
                "has_missing_core_gap": any_missing_core_gap,
                "corporate_event_clear": not any_unresolved_event,
            }
        )
        latest_missing_core_gap = any_missing_core_gap
        latest_corporate_event_clear = not any_unresolved_event
        latest_execution_universe_count = execution_universe_count
        latest_bucket_coverages = bucket_coverages

    stale_mark_days_with_open_positions = 0
    weights = weights.reindex(columns=request.symbols).fillna(0.0)
    volume_df = volume_df.reindex(index=weights.index, columns=request.symbols)
    for trading_dt, row in weights.iterrows():
        open_positions = [symbol for symbol, value in row.items() if float(value) > 0]
        if not open_positions:
            continue
        stale_detected = False
        for symbol in open_positions:
            volume_value = (
                volume_df.at[trading_dt, symbol]
                if symbol in volume_df.columns
                else None
            )
            if pd.isna(volume_value) or float(volume_value) <= 0:
                stale_detected = True
                break
        if stale_detected:
            stale_mark_days_with_open_positions += 1

    stale_risk_share = (
        float(stale_mark_days_with_open_positions / len(trading_dates))
        if trading_dates
        else 0.0
    )

    corporate_event_state = (
        "clear" if latest_corporate_event_clear else "unresolved_corporate_event"
    )
    if corporate_event_state == "unresolved_corporate_event":
        tradability_state = "unresolved_corporate_event"
    elif stale_mark_days_with_open_positions > 0:
        tradability_state = "stale_risk"
    elif latest_execution_universe_count > 0:
        tradability_state = "execution_ready"
    else:
        tradability_state = "research_only"

    missing_feature_policy_state = (
        "core_data_gaps_filtered"
        if latest_missing_core_gap
        else "native_missing_supported"
    )

    microstructure_observations = []
    if request.monitor_profile_id == MONITOR_PROFILE_ID:
        stale_by_date = {
            trading_dt.date(): False
            for trading_dt in pd.to_datetime(weights.index).unique()
        }
        for trading_dt, row in weights.iterrows():
            open_positions = [
                symbol for symbol, value in row.items() if float(value) > 0
            ]
            if not open_positions:
                continue
            stale_detected = False
            for symbol in open_positions:
                volume_value = (
                    volume_df.at[trading_dt, symbol]
                    if symbol in volume_df.columns
                    else None
                )
                if pd.isna(volume_value) or float(volume_value) <= 0:
                    stale_detected = True
                    break
            if stale_detected:
                stale_by_date[trading_dt.date()] = True

        microstructure_observations = [
            {
                "monitor_profile_id": MONITOR_PROFILE_ID,
                "market": request.market,
                "trading_date": item["trading_date"],
                "full_universe_count": item["full_universe_count"],
                "execution_universe_count": item["execution_universe_count"],
                "execution_universe_ratio": item["execution_universe_ratio"],
                "stale_mark_with_open_positions": stale_by_date.get(
                    item["trading_date"], False
                ),
                "liquidity_bucket_schema_version": LIQUIDITY_BUCKET_SCHEMA_VERSION,
                "bucket_coverages": item["bucket_coverages"],
            }
            for item in daily_observations
        ]

    monitor_observation_status = "not_requested"
    if request.monitor_profile_id == MONITOR_PROFILE_ID:
        monitor_observation_status = (
            "persisted" if microstructure_observations else "skipped"
        )

    return {
        "tradability_state": tradability_state,
        "tradability_contract_version": ACTIVE_TRADABILITY_CONTRACT_VERSION,
        "capacity_screening_active": capacity_screening_active,
        "missing_feature_policy_state": missing_feature_policy_state,
        "corporate_event_state": corporate_event_state,
        "full_universe_count": full_universe_count,
        "execution_universe_count": latest_execution_universe_count,
        "execution_universe_ratio": (
            float(latest_execution_universe_count / full_universe_count)
            if full_universe_count > 0
            else 0.0
        ),
        "liquidity_bucket_schema_version": LIQUIDITY_BUCKET_SCHEMA_VERSION,
        "liquidity_bucket_coverages": latest_bucket_coverages,
        "stale_mark_days_with_open_positions": stale_mark_days_with_open_positions,
        "stale_risk_share": stale_risk_share,
        "monitor_observation_status": monitor_observation_status,
        "monitor_profile_id": request.monitor_profile_id,
        "microstructure_observations": microstructure_observations,
        "adv_basis_version": ADV_BASIS_VERSION,
        # The declared contract stays stable even when `capacity_screening_active`
        # is false for a particular run.
        "capacity_screening_version": CAPACITY_SCREENING_VERSION,
        "missing_feature_policy_version": MISSING_FEATURE_POLICY_VERSION,
        "execution_cost_model_version": EXECUTION_COST_MODEL_VERSION,
        # P3 intentionally stays research-only on investability until TBD-001 closes.
        "investability_screening_active": False,
    }
