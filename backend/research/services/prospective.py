"""Small, auditable helpers for manual TW prospective-evidence cohorts."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.database import DailyOHLCV, ResearchRun, SessionLocal
from backend.market_data.repositories.company_profiles import list_tw_company_profiles
from backend.platform.db.repository_helpers import json_loads
from backend.platform.errors import UnsupportedConfigurationError
from backend.research.contracts.runs import ResearchRunCreateRequest
from backend.research.domain.prospective_recipe import (
    COHORT_2330,
    COHORT_ALL_ACTIVE,
    COHORT_IDS,
    MIN_EXECUTION_COVERAGE,
    STRICT_MODE,
    build_strict_request_payload,
    strict_recipe_issues,
)
from backend.research.repositories.runs import get_research_run_record
from backend.research.services.eligibility import (
    exclude_non_official_rows_on_official_no_data,
    load_official_no_data_dates,
)
from backend.research.services.execution import (
    build_feature_config,
    build_forward_opinion_signals,
    load_symbol_data,
)
from backend.shared.analytics.strategy import resolve_runtime_strategy
from scripts.market_data_ingestion import OFFICIAL_SOURCES

TW_TIMEZONE = ZoneInfo("Asia/Taipei")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EligibleBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    source: str
    raw_payload_id: int | None


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def active_tw_profile_symbols() -> list[str]:
    """Active TWSE/TPEX profiles only; deliberately no lifecycle overlay."""
    return sorted(
        {
            str(record["symbol"]).upper()
            for record in list_tw_company_profiles(limit=0, trading_status="active")
            if str(record.get("market") or "").upper() == "TW"
            and str(record.get("exchange") or "").upper() in {"TWSE", "TPEX"}
            and str(record.get("symbol") or "").strip()
        }
    )


def load_eligible_bars(
    symbols: Iterable[str], *, start_date: date, end_date: date | None = None
) -> dict[str, list[EligibleBar]]:
    """Load research-eligible rows without mutating data or making network calls."""
    requested = sorted({str(item).strip().upper() for item in symbols if str(item).strip()})
    if not requested:
        return {}
    with SessionLocal() as session:
        stmt = (
            select(DailyOHLCV)
            .where(DailyOHLCV.market == "TW")
            .where(DailyOHLCV.symbol.in_(requested))
            .where(DailyOHLCV.date >= start_date)
            .order_by(DailyOHLCV.symbol.asc(), DailyOHLCV.date.asc())
        )
        if end_date is not None:
            stmt = stmt.where(DailyOHLCV.date <= end_date)
        rows = session.execute(stmt).scalars().all()

    # The existing eligibility rule is dataframe based; avoid duplicating its audit logic.
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "date": row.date,
                "symbol": row.symbol,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "source": row.source,
                "raw_payload_id": row.raw_payload_id,
            }
            for row in rows
        ]
    )
    if frame.empty:
        return {}
    frame = frame.set_index("date")
    frame = exclude_non_official_rows_on_official_no_data(
        frame,
        load_official_no_data_dates(
            start_date=start_date,
            end_date=end_date or datetime.now(TW_TIMEZONE).date(),
        ),
    )
    result: dict[str, list[EligibleBar]] = defaultdict(list)
    for row in frame.reset_index().itertuples(index=False):
        values = [row.open, row.high, row.low, row.close]
        if not all(math.isfinite(float(value)) and float(value) > 0 for value in values):
            continue
        result[str(row.symbol).upper()].append(
            EligibleBar(
                date=_as_date(row.date) or row.date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                source=str(row.source),
                raw_payload_id=row.raw_payload_id,
            )
        )
    return dict(result)


def strict_request_payload(
    *, symbols: list[str], basis_date: date, cohort_id: str, full_universe_symbols: list[str]
) -> dict[str, Any]:
    return build_strict_request_payload(
        symbols=symbols,
        basis_date=basis_date,
        cohort_id=cohort_id,
        full_universe_symbols=full_universe_symbols,
    )


def _model_ready_symbol(
    *, request: ResearchRunCreateRequest, symbol: str, feature_config: dict, shift_map: dict,
    official_no_data_dates: set[date], basis_date: date,
) -> str | None:
    """Return an exclusion reason, or None only after the exact model path is usable."""
    try:
        result = load_symbol_data(
            "prospective-preflight-no-write",
            request,
            symbol,
            feature_config,
            shift_map,
            request.validation.test_size if request.validation else 0.2,
            official_no_data_dates=official_no_data_dates,
        )
        prospective_features = result["prospective_prediction_features"]
        if prospective_features.index.max().date() != basis_date:
            return "basis_date_not_latest_feature_date"
        if result.get("direction_unavailable_reason"):
            return "direction_calibration_unavailable"
        runtime_context = resolve_runtime_strategy(
            strategy=request.strategy,
            runtime_mode=request.runtime_mode,
            default_bundle_version=request.default_bundle_version,
        )
        signals, warning = build_forward_opinion_signals(
            [result], request, runtime_context["strategy"]
        )
        if warning or len(signals) != 1:
            return "forward_signal_unavailable"
        return None
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc) or 'model_preflight_failed'}"


def preflight_cohort(*, cohort_id: str, basis_date: date) -> dict[str, Any]:
    full_symbols = ["2330"] if cohort_id == COHORT_2330 else active_tw_profile_symbols()
    exclusions: dict[str, str] = {}
    if full_symbols:
        feature_config, shift_map = build_feature_config(
            ResearchRunCreateRequest.model_validate(
                strict_request_payload(
                    symbols=[full_symbols[0]],
                    basis_date=basis_date,
                    cohort_id=cohort_id,
                    full_universe_symbols=full_symbols,
                )
            )
        )
        official_no_data_dates = load_official_no_data_dates(
            start_date=basis_date - timedelta(days=1096), end_date=basis_date
        )
        total_symbols = len(full_symbols)
        for index, symbol in enumerate(full_symbols, start=1):
            request = ResearchRunCreateRequest.model_validate(
                strict_request_payload(
                    symbols=[symbol],
                    basis_date=basis_date,
                    cohort_id=cohort_id,
                    full_universe_symbols=full_symbols,
                )
            )
            reason = _model_ready_symbol(
                request=request,
                symbol=symbol,
                feature_config=feature_config,
                shift_map=shift_map,
                official_no_data_dates=official_no_data_dates,
                basis_date=basis_date,
            )
            if reason is not None:
                exclusions[symbol] = reason
            if cohort_id == COHORT_ALL_ACTIVE and (
                index % 100 == 0 or index == total_symbols
            ):
                logger.info(
                    "Prospective preflight progress cohort_id=%s basis_date=%s "
                    "processed=%d total=%d exclusions=%d",
                    cohort_id,
                    basis_date,
                    index,
                    total_symbols,
                    len(exclusions),
                )
    execution_symbols = [symbol for symbol in full_symbols if symbol not in exclusions]
    coverage = len(execution_symbols) / len(full_symbols) if full_symbols else 0.0
    ready = (
        execution_symbols == ["2330"]
        if cohort_id == COHORT_2330
        else coverage >= MIN_EXECUTION_COVERAGE
    )
    reason = None
    if not ready:
        reason = (
            f"Symbol 2330 is not model-ready: "
            f"{exclusions.get('2330', 'excluded')}."
            if cohort_id == COHORT_2330
            else (
                f"Execution coverage {coverage:.2%} is below "
                f"{MIN_EXECUTION_COVERAGE:.0%}."
            )
        )
    return {
        "cohort_id": cohort_id,
        "basis_date": basis_date.isoformat(),
        "full_universe_symbols": full_symbols,
        "execution_symbols": execution_symbols,
        "full_universe_count": len(full_symbols),
        "execution_universe_count": len(execution_symbols),
        "execution_coverage_ratio": coverage,
        "exclusions": exclusions,
        "exclusion_count": len(exclusions),
        "status": "ready" if ready else "no-opinion",
        "reason": reason,
    }


def _run_evidence(record: dict[str, Any]) -> dict[str, Any] | None:
    payload = record.get("request_payload")
    if not isinstance(payload, dict):
        return None
    evidence = payload.get("prospective_evidence")
    return evidence if isinstance(evidence, dict) else None


def list_cohort_run_records(cohort_id: str) -> list[dict[str, Any]]:
    if cohort_id not in COHORT_IDS:
        raise ValueError(f"Unknown prospective cohort '{cohort_id}'.")
    with SessionLocal() as session:
        rows = session.execute(
            select(ResearchRun.run_id, ResearchRun.request_payload_json)
            .where(
                ResearchRun.request_payload_json.contains(
                    '"cohort_id"', autoescape=True
                )
            )
            .where(
                ResearchRun.request_payload_json.contains(
                    f'"{cohort_id}"', autoescape=True
                )
            )
            .order_by(ResearchRun.created_at.asc(), ResearchRun.run_id.asc())
        ).all()
    records = []
    for run_id, request_payload_json in rows:
        request_payload = json_loads(request_payload_json, None)
        evidence = (
            request_payload.get("prospective_evidence")
            if isinstance(request_payload, dict)
            else None
        )
        if not isinstance(evidence, dict) or evidence.get("cohort_id") != cohort_id:
            continue
        record = get_research_run_record(run_id)
        loaded_evidence = _run_evidence(record)
        if loaded_evidence and loaded_evidence.get("cohort_id") == cohort_id:
            records.append(record)
    return records


def _strict_run_issues(record: dict[str, Any], *, cohort_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    evidence = _run_evidence(record)
    issues: list[str] = []
    if record.get("status") != "succeeded":
        issues.append("run_not_succeeded")
    if not evidence or evidence.get("mode") != STRICT_MODE or evidence.get("cohort_id") != cohort_id:
        issues.append("missing_strict_evidence")
        return None, issues
    basis_date = _as_date(evidence.get("basis_date"))
    signal_frozen_at = _as_datetime(evidence.get("signal_frozen_at"))
    if basis_date is None:
        issues.append("invalid_basis_date")
    if signal_frozen_at is None or signal_frozen_at.tzinfo is None:
        issues.append("invalid_signal_frozen_at")
    elif basis_date is not None and signal_frozen_at.astimezone(TW_TIMEZONE).date() != basis_date:
        issues.append("signal_frozen_at_not_on_basis_date")
    payload = record.get("request_payload") or {}
    if isinstance(payload, dict):
        issues.extend(
            issue
            for issue in strict_recipe_issues(payload)
            if issue not in issues
        )
        if evidence.get("cohort_id") == COHORT_ALL_ACTIVE:
            snapshot = evidence.get("full_universe_symbols")
            symbols = payload.get("symbols")
            if isinstance(snapshot, list) and isinstance(symbols, list):
                snapshot_set = {str(item).upper() for item in snapshot}
                symbols_set = {str(item).upper() for item in symbols}
                if (
                    not snapshot_set
                    or not symbols_set
                    or not symbols_set.issubset(snapshot_set)
                    or len(symbols_set) / len(snapshot_set)
                    < MIN_EXECUTION_COVERAGE
                ):
                    issues.append("strict_execution_coverage_mismatch")
    else:
        issues.append("missing_strict_evidence")
    return evidence, issues


def _forward_signal_issues(
    record: dict[str, Any], *, basis_date: date | None
) -> list[str]:
    signals = [
        item
        for item in record.get("signals", [])
        if item.get("signal_kind") == "forward_opinion"
    ]
    requested = set((record.get("request_payload") or {}).get("symbols", []))
    if (
        basis_date is None
        or {str(item.get("symbol") or "").upper() for item in signals}
        != {str(item).upper() for item in requested}
        or len(signals) != len(requested)
        or any(_as_date(item.get("date")) != basis_date for item in signals)
    ):
        return ["incomplete_forward_signals"]
    if any(
        _finite_number(item.get("score")) is None
        or (probability := _finite_number(item.get("up_probability"))) is None
        or not 0 <= probability <= 1
        or (position := _finite_number(item.get("position"))) is None
        or position < 0
        for item in signals
    ):
        return ["invalid_forward_signal"]
    return []


def valid_successful_cohort_runs(
    *, cohort_id: str, basis_date: date
) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for record in list_cohort_run_records(cohort_id):
        evidence, issues = _strict_run_issues(record, cohort_id=cohort_id)
        record_basis_date = _as_date((evidence or {}).get("basis_date"))
        issues.extend(
            _forward_signal_issues(record, basis_date=record_basis_date)
        )
        if record_basis_date == basis_date and not issues:
            valid.append(record)
    return valid


def prospective_run_id(*, cohort_id: str, basis_date: date) -> str:
    if cohort_id not in COHORT_IDS:
        raise ValueError(f"Unknown prospective cohort '{cohort_id}'.")
    return str(
        uuid5(
            NAMESPACE_URL,
            f"web-predict-stock:prospective:{cohort_id}:{basis_date.isoformat()}",
        )
    )


def validate_strict_cohort_start(
    request: ResearchRunCreateRequest, *, run_id: str
) -> None:
    evidence = request.prospective_evidence
    if evidence is None:
        return
    expected_snapshot = (
        ["2330"]
        if evidence.cohort_id == COHORT_2330
        else active_tw_profile_symbols()
    )
    if evidence.full_universe_symbols != expected_snapshot:
        raise UnsupportedConfigurationError(
            "strict prospective evidence full_universe_symbols do not match "
            "the current cohort snapshot"
        )
    if (
        evidence.cohort_id == COHORT_ALL_ACTIVE
        and len(request.symbols) / len(evidence.full_universe_symbols)
        < MIN_EXECUTION_COVERAGE
    ):
        raise UnsupportedConfigurationError(
            "strict prospective evidence execution coverage is below "
            f"{MIN_EXECUTION_COVERAGE:.0%}"
        )
    existing = [
        record
        for record in valid_successful_cohort_runs(
            cohort_id=evidence.cohort_id,
            basis_date=evidence.basis_date,
        )
        if record.get("run_id") != run_id
    ]
    if existing:
        raise UnsupportedConfigurationError(
            "a valid strict prospective run already exists for "
            f"cohort={evidence.cohort_id} basis_date={evidence.basis_date.isoformat()}"
        )


def _finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _signal_outcome(
    signal: dict[str, Any],
    *,
    basis_date: date,
    bars_by_symbol: dict[str, list[EligibleBar]],
) -> dict[str, Any]:
    symbol = str(signal.get("symbol") or "").upper()
    bars = bars_by_symbol.get(symbol, [])
    basis = next((bar for bar in bars if bar.date == basis_date), None)
    later = [bar for bar in bars if bar.date > basis_date]
    if len(later) < 2:
        return {"symbol": symbol, "status": "not_ready"}
    entry, exit_ = later[:2]
    if basis is None or any(bar.source not in OFFICIAL_SOURCES for bar in (basis, entry, exit_)):
        return {"symbol": symbol, "status": "not_ready", "reason": "official_outcomes_unavailable"}
    actual_return = exit_.open / entry.open - 1.0
    score = _finite_number(signal.get("score"))
    probability = _finite_number(signal.get("up_probability"))
    position = _finite_number(signal.get("position"))
    if score is None or probability is None or not 0 <= probability <= 1 or position is None or position < 0:
        return {"symbol": symbol, "status": "invalid_signal"}
    direction = int(actual_return > 0)
    return {
        "symbol": symbol,
        "status": "resolved",
        "entry_date": entry.date.isoformat(),
        "exit_date": exit_.date.isoformat(),
        "basis_source": basis.source,
        "entry_source": entry.source,
        "exit_source": exit_.source,
        "actual_return": actual_return,
        "actual_direction": direction,
        "score": score,
        "up_probability": probability,
        "position": position,
        "brier": (probability - direction) ** 2,
        "direction_hit": int((probability >= 0.5) == bool(direction)),
        "gross_position_return": position * actual_return,
    }


def _net_return(actual_return: float, position: float, *, fees: float, slippage: float) -> float:
    if position <= 0:
        return 0.0
    # Same two-side percentage fee/slippage semantics as the existing vectorbt path.
    return position * (((1 + actual_return) * (1 - slippage) / (1 + slippage) * (1 - fees) ** 2) - 1)


def _correlation(points: list[dict[str, Any]], method: str) -> float | None:
    if len(points) < 2:
        return None
    try:
        import pandas as pd

        value = pd.Series([item["actual_return"] for item in points]).corr(
            pd.Series([item["score"] for item in points]), method=method
        )
        return float(value) if value is not None and math.isfinite(float(value)) else None
    except (TypeError, ValueError):
        logger.warning(
            "Failed to calculate prospective correlation method=%s point_count=%d",
            method,
            len(points),
            exc_info=True,
        )
        return None


def _compound_daily(points: list[dict[str, Any]], field: str, *, weighted: bool) -> float | None:
    if not points:
        return None
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        by_day[point["basis_date"]].append(point)
    total = 1.0
    for day_points in by_day.values():
        if weighted:
            daily_return = sum(float(item[field]) for item in day_points)
        else:
            daily_return = mean(float(item[field]) for item in day_points)
        total *= 1.0 + daily_return
    return total - 1.0


def evaluate_cohort(cohort_id: str) -> dict[str, Any]:
    """Read persisted strict runs and calculate only already-observable outcomes."""
    records = list_cohort_run_records(cohort_id)
    prepared: list[
        tuple[dict[str, Any], dict[str, Any] | None, date | None, list[str]]
    ] = []
    basis_counts: dict[date, int] = defaultdict(int)
    for record in records:
        evidence, issues = _strict_run_issues(record, cohort_id=cohort_id)
        basis_date = _as_date((evidence or {}).get("basis_date"))
        issues.extend(_forward_signal_issues(record, basis_date=basis_date))
        prepared.append((record, evidence, basis_date, issues))
        if basis_date is not None and not issues:
            basis_counts[basis_date] += 1

    for _, _, basis_date, issues in prepared:
        if basis_date is not None and basis_counts[basis_date] > 1:
            issues.append("duplicate_basis_date")

    evaluable = [
        (record, basis_date)
        for record, _, basis_date, issues in prepared
        if basis_date is not None and not issues
    ]
    outcome_symbols = sorted(
        {
            str(item.get("symbol") or "").upper()
            for record, _ in evaluable
            for item in record.get("signals", [])
            if item.get("signal_kind") == "forward_opinion"
            and str(item.get("symbol") or "").strip()
        }
    )
    bars_by_symbol = (
        load_eligible_bars(
            outcome_symbols,
            start_date=min(basis_date for _, basis_date in evaluable),
            end_date=datetime.now(TW_TIMEZONE).date(),
        )
        if evaluable and outcome_symbols
        else {}
    )

    run_reports: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    valid_costs: set[tuple[float, float]] = set()
    for record, evidence, basis_date, issues in prepared:
        signals = [
            item
            for item in record.get("signals", [])
            if item.get("signal_kind") == "forward_opinion"
        ]
        execution = (record.get("request_payload") or {}).get("execution", {})
        fees = _finite_number(execution.get("fees"))
        slippage = _finite_number(execution.get("slippage"))
        if not issues and fees is not None and slippage is not None:
            valid_costs.add((fees, slippage))
        if issues or basis_date is None:
            outcomes = []
        else:
            outcomes = [
                _signal_outcome(
                    item,
                    basis_date=basis_date,
                    bars_by_symbol=bars_by_symbol,
                )
                for item in signals
            ]
        if any(item["status"] == "invalid_signal" for item in outcomes):
            issues.append("invalid_forward_signal")
        if not issues and basis_date is not None:
            for outcome in outcomes:
                if outcome["status"] == "resolved":
                    outcome["basis_date"] = basis_date.isoformat()
                    outcome["net_position_return"] = (
                        _net_return(
                            outcome["actual_return"],
                            outcome["position"],
                            fees=fees,
                            slippage=slippage,
                        )
                        if fees is not None and slippage is not None
                        else None
                    )
        report = {
            "run_id": record["run_id"],
            "basis_date": basis_date.isoformat() if basis_date else None,
            "status": "invalid" if issues else "not_ready" if any(item["status"] == "not_ready" for item in outcomes) else "resolved",
            "issues": issues,
            "outcomes": outcomes,
        }
        if report["status"] == "resolved":
            report["gross_portfolio_return"] = sum(
                item["gross_position_return"] for item in outcomes
            )
            net_returns = [item.get("net_position_return") for item in outcomes]
            report["net_portfolio_return"] = (
                sum(float(value) for value in net_returns)
                if all(value is not None for value in net_returns)
                else None
            )
        run_reports.append(report)
        if report["status"] == "resolved":
            resolved.extend(outcomes)

    fees_value = next(iter(valid_costs))[0] if len(valid_costs) == 1 else None
    slippage_value = next(iter(valid_costs))[1] if len(valid_costs) == 1 else None
    errors = [item["actual_return"] - item["score"] for item in resolved]
    resolved_reports = [
        item for item in run_reports if item["status"] == "resolved"
    ]
    net_return_points = [
        {
            "basis_date": item["basis_date"],
            "return": item["net_portfolio_return"],
        }
        for item in resolved_reports
        if item.get("net_portfolio_return") is not None
    ]
    return {
        "cohort_id": cohort_id,
        "runs": run_reports,
        "completed_trading_days": len({item["basis_date"] for item in run_reports if item["status"] == "resolved"}),
        "resolved_signal_count": len(resolved),
        "metrics": {
            "rmse": (mean(error * error for error in errors) ** 0.5) if errors else None,
            "mae": mean(abs(error) for error in errors) if errors else None,
            "pearson_ic": _correlation(resolved, "pearson"),
            "spearman_ic": _correlation(resolved, "spearman"),
            "direction_accuracy": mean(item["direction_hit"] for item in resolved) if resolved else None,
            "brier": mean(item["brier"] for item in resolved) if resolved else None,
            "active_position_share": mean(item["position"] > 0 for item in resolved) if resolved else None,
            "gross_position_return": _compound_daily(
                [
                    {
                        "basis_date": item["basis_date"],
                        "return": item["gross_portfolio_return"],
                    }
                    for item in resolved_reports
                ],
                "return", weighted=True,
            ),
            "net_position_return": (
                _compound_daily(net_return_points, "return", weighted=True)
                if len(net_return_points) == len(resolved_reports)
                and fees_value is not None
                and slippage_value is not None
                else None
            ),
            "matched_equal_weight_benchmark_return": _compound_daily(resolved, "actual_return", weighted=False),
        },
        "costs": {"fees": fees_value, "slippage": slippage_value},
    }
