from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, desc, select

from backend.database import (
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
    SessionLocal,
)
from backend.research.domain.version_pack import build_version_pack_payload
from backend.platform.errors import DataAccessError, DataNotFoundError
from backend.platform.time import utc_now
from backend.platform.db.repository_helpers import (
    clone_payload,
    json_dumps,
    json_loads,
    normalize_created_at,
)

logger = logging.getLogger(__name__)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def _validation_summary_from_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if "method" not in value or "metrics" not in value:
        return None
    if value["method"] not in {
        "holdout",
        "walk_forward",
        "rolling_window",
        "expanding_window",
    }:
        return None
    if not isinstance(value["metrics"], dict):
        return None
    for metric_value in value["metrics"].values():
        if not isinstance(metric_value, int | float):
            return None
    return value


def _model_diagnostics_from_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("task") != "regression":
        return None
    try:
        sample_count = int(value.get("sample_count", 0))
    except (TypeError, ValueError):
        return None

    payload = {
        "task": "regression",
        "sample_count": sample_count,
        "rmse": value.get("rmse"),
        "mae": value.get("mae"),
        "rank_ic": value.get("rank_ic"),
        "linear_ic": value.get("linear_ic"),
        "actual_vs_predicted": value.get("actual_vs_predicted", []),
        "residuals": value.get("residuals", []),
        "feature_importance": value.get("feature_importance", []),
    }
    for key in ("rmse", "mae", "rank_ic", "linear_ic"):
        if payload[key] is not None and not isinstance(payload[key], int | float):
            payload[key] = None
    for key in ("actual_vs_predicted", "residuals", "feature_importance"):
        if not isinstance(payload[key], list):
            payload[key] = []
    return payload


def _summarize_model_diagnostics(value: Any) -> dict[str, Any] | None:
    payload = _model_diagnostics_from_payload(value)
    if payload is None:
        return None
    return {
        **payload,
        "actual_vs_predicted": [],
        "residuals": [],
        "feature_importance": [],
    }


def _run_row_to_dict(row: ResearchRun, *, include_artifacts: bool = True) -> dict[str, Any]:
    effective_strategy = None
    if row.effective_threshold is not None and row.effective_top_n is not None:
        effective_strategy = {
            "threshold": row.effective_threshold,
            "top_n": row.effective_top_n,
        }

    validation_outcome = json_loads(row.validation_outcome_json, None)
    model_diagnostics = json_loads(row.model_diagnostics_json, None)
    payload = {
        "run_id": row.run_id,
        "request_id": row.request_id,
        "status": row.status,
        "market": row.market,
        "symbols": json_loads(row.symbols_json, []),
        "strategy_type": row.strategy_type,
        "runtime_mode": row.runtime_mode,
        "default_bundle_version": row.default_bundle_version,
        "effective_strategy": effective_strategy,
        "allow_proactive_sells": row.allow_proactive_sells,
        "config_sources": json_loads(row.config_sources_json, None),
        "fallback_audit": json_loads(row.fallback_audit_json, None),
        "validation_outcome": validation_outcome,
        "rejection_reason": row.rejection_reason,
        "request_payload": json_loads(row.request_payload_json, None),
        "metrics": json_loads(row.metrics_json, None),
        "equity_curve": json_loads(row.equity_curve_json, [])
        if include_artifacts
        else [],
        "signals": json_loads(row.signals_json, []) if include_artifacts else [],
        "validation": _validation_summary_from_payload(validation_outcome),
        "model_diagnostics": _model_diagnostics_from_payload(model_diagnostics)
        if include_artifacts
        else _summarize_model_diagnostics(model_diagnostics),
        "baselines": json_loads(row.baselines_json, {}),
        "warnings": json_loads(row.warnings_json, []),
        "factor_catalog_version": row.factor_catalog_version,
        "scoring_factor_ids": json_loads(row.scoring_factor_ids_json, []),
        "external_signal_policy_version": row.external_signal_policy_version,
        "external_lineage_version": row.external_lineage_version,
        "cluster_snapshot_version": row.cluster_snapshot_version,
        "peer_policy_version": row.peer_policy_version,
        "peer_comparison_policy_version": row.peer_comparison_policy_version,
        "execution_route": row.execution_route,
        "simulation_profile_id": row.simulation_profile_id,
        "simulation_adapter_version": row.simulation_adapter_version,
        "live_control_profile_id": row.live_control_profile_id,
        "live_control_version": row.live_control_version,
        "adaptive_mode": row.adaptive_mode,
        "adaptive_profile_id": row.adaptive_profile_id,
        "adaptive_contract_version": row.adaptive_contract_version,
        "reward_definition_version": row.reward_definition_version,
        "state_definition_version": row.state_definition_version,
        "rollout_control_version": row.rollout_control_version,
        "tradability_state": row.tradability_state,
        "tradability_contract_version": row.tradability_contract_version,
        "capacity_screening_active": row.capacity_screening_active,
        "missing_feature_policy_state": row.missing_feature_policy_state,
        "corporate_event_state": row.corporate_event_state,
        "full_universe_count": row.full_universe_count,
        "execution_universe_count": row.execution_universe_count,
        "execution_universe_ratio": row.execution_universe_ratio,
        "liquidity_bucket_schema_version": row.liquidity_bucket_schema_version,
        "liquidity_bucket_coverages": [],
        "stale_mark_days_with_open_positions": row.stale_mark_days_with_open_positions,
        "stale_risk_share": row.stale_risk_share,
        "monitor_observation_status": row.monitor_observation_status,
        "created_at": normalize_created_at(row.created_at),
    }
    payload.update(
        build_version_pack_payload(
            {
                "threshold_policy_version": row.threshold_policy_version,
                "price_basis_version": row.price_basis_version,
                "benchmark_comparability_gate": row.benchmark_comparability_gate,
                "comparison_eligibility": row.comparison_eligibility,
                "investability_screening_active": row.investability_screening_active,
                "capacity_screening_version": row.capacity_screening_version,
                "adv_basis_version": row.adv_basis_version,
                "missing_feature_policy_version": row.missing_feature_policy_version,
                "execution_cost_model_version": row.execution_cost_model_version,
                "split_policy_version": row.split_policy_version,
                "bootstrap_policy_version": row.bootstrap_policy_version,
                "ic_overlap_policy_version": row.ic_overlap_policy_version,
                "comparison_review_matrix_version": (
                    row.comparison_review_matrix_version
                ),
                "scheduled_review_cadence": row.scheduled_review_cadence,
                "model_family": row.model_family,
                "training_output_contract_version": (
                    row.training_output_contract_version
                ),
                "adoption_comparison_policy_version": (
                    row.adoption_comparison_policy_version
                ),
                "factor_catalog_version": row.factor_catalog_version,
                "external_signal_policy_version": row.external_signal_policy_version,
                "external_lineage_version": row.external_lineage_version,
                "cluster_snapshot_version": row.cluster_snapshot_version,
                "peer_policy_version": row.peer_policy_version,
                "peer_comparison_policy_version": row.peer_comparison_policy_version,
                "execution_route": row.execution_route,
                "simulation_profile_id": row.simulation_profile_id,
                "simulation_adapter_version": row.simulation_adapter_version,
                "live_control_profile_id": row.live_control_profile_id,
                "live_control_version": row.live_control_version,
                "adaptive_mode": row.adaptive_mode,
                "adaptive_profile_id": row.adaptive_profile_id,
                "adaptive_contract_version": row.adaptive_contract_version,
                "reward_definition_version": row.reward_definition_version,
                "state_definition_version": row.state_definition_version,
                "rollout_control_version": row.rollout_control_version,
                "scoring_factor_ids": json_loads(row.scoring_factor_ids_json, []),
            }
        )
    )
    return payload


def _attach_liquidity_coverages(
    session: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    stmt = (
        select(ResearchRunLiquidityCoverage)
        .where(ResearchRunLiquidityCoverage.run_id == payload["run_id"])
        .order_by(ResearchRunLiquidityCoverage.bucket_key.asc())
    )
    payload["liquidity_bucket_coverages"] = [
        {
            "bucket_key": row.bucket_key,
            "bucket_label": row.bucket_label,
            "full_universe_count": row.full_universe_count,
            "execution_universe_count": row.execution_universe_count,
            "full_universe_ratio": row.full_universe_ratio,
            "execution_coverage_ratio": row.execution_coverage_ratio,
        }
        for row in session.execute(stmt).scalars().all()
    ]
    return payload


def persist_research_run_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("symbols", [])
    record.setdefault("warnings", [])
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, record["run_id"]) or ResearchRun(
                run_id=record["run_id"]
            )
            row.request_id = record.get("request_id")
            row.status = record["status"]
            row.market = record.get("market")
            row.symbols_json = json_dumps(record.get("symbols", [])) or "[]"
            row.strategy_type = record.get("strategy_type")
            row.runtime_mode = record.get("runtime_mode")
            row.default_bundle_version = record.get("default_bundle_version")
            effective_strategy = record.get("effective_strategy") or {}
            row.effective_threshold = effective_strategy.get("threshold")
            row.effective_top_n = effective_strategy.get("top_n")
            row.allow_proactive_sells = record.get("allow_proactive_sells")
            row.config_sources_json = json_dumps(record.get("config_sources"))
            row.fallback_audit_json = json_dumps(record.get("fallback_audit"))
            row.validation_outcome_json = json_dumps(record.get("validation_outcome"))
            row.rejection_reason = record.get("rejection_reason")
            row.request_payload_json = json_dumps(record.get("request_payload"))
            row.metrics_json = json_dumps(record.get("metrics"))
            row.equity_curve_json = json_dumps(record.get("equity_curve", []))
            row.signals_json = json_dumps(record.get("signals", []))
            row.model_diagnostics_json = json_dumps(
                record.get("model_diagnostics")
            )
            row.baselines_json = json_dumps(record.get("baselines", {}))
            row.warnings_json = json_dumps(record.get("warnings", []))
            row.factor_catalog_version = record.get("factor_catalog_version")
            row.scoring_factor_ids_json = json_dumps(
                record.get("scoring_factor_ids", [])
            )
            row.external_signal_policy_version = record.get(
                "external_signal_policy_version"
            )
            row.external_lineage_version = record.get("external_lineage_version")
            row.cluster_snapshot_version = record.get("cluster_snapshot_version")
            row.peer_policy_version = record.get("peer_policy_version")
            row.peer_comparison_policy_version = record.get(
                "peer_comparison_policy_version"
            )
            row.execution_route = record.get("execution_route")
            row.simulation_profile_id = record.get("simulation_profile_id")
            row.simulation_adapter_version = record.get("simulation_adapter_version")
            row.live_control_profile_id = record.get("live_control_profile_id")
            row.live_control_version = record.get("live_control_version")
            row.adaptive_mode = record.get("adaptive_mode")
            row.adaptive_profile_id = record.get("adaptive_profile_id")
            row.adaptive_contract_version = record.get("adaptive_contract_version")
            row.reward_definition_version = record.get("reward_definition_version")
            row.state_definition_version = record.get("state_definition_version")
            row.rollout_control_version = record.get("rollout_control_version")
            row.threshold_policy_version = record.get("threshold_policy_version")
            row.price_basis_version = record.get("price_basis_version")
            row.benchmark_comparability_gate = record.get(
                "benchmark_comparability_gate"
            )
            row.comparison_eligibility = record.get("comparison_eligibility")
            row.investability_screening_active = record.get(
                "investability_screening_active"
            )
            row.capacity_screening_active = record.get("capacity_screening_active")
            row.capacity_screening_version = record.get("capacity_screening_version")
            row.adv_basis_version = record.get("adv_basis_version")
            row.missing_feature_policy_version = record.get(
                "missing_feature_policy_version"
            )
            row.execution_cost_model_version = record.get(
                "execution_cost_model_version"
            )
            row.split_policy_version = record.get("split_policy_version")
            row.bootstrap_policy_version = record.get("bootstrap_policy_version")
            row.ic_overlap_policy_version = record.get("ic_overlap_policy_version")
            row.comparison_review_matrix_version = record.get(
                "comparison_review_matrix_version"
            )
            row.scheduled_review_cadence = record.get("scheduled_review_cadence")
            row.model_family = record.get("model_family")
            row.training_output_contract_version = record.get(
                "training_output_contract_version"
            )
            row.adoption_comparison_policy_version = record.get(
                "adoption_comparison_policy_version"
            )
            row.tradability_state = record.get("tradability_state")
            row.tradability_contract_version = record.get(
                "tradability_contract_version"
            )
            row.missing_feature_policy_state = record.get(
                "missing_feature_policy_state"
            )
            row.corporate_event_state = record.get("corporate_event_state")
            row.full_universe_count = record.get("full_universe_count")
            row.execution_universe_count = record.get("execution_universe_count")
            row.execution_universe_ratio = record.get("execution_universe_ratio")
            row.liquidity_bucket_schema_version = record.get(
                "liquidity_bucket_schema_version"
            )
            row.stale_mark_days_with_open_positions = record.get(
                "stale_mark_days_with_open_positions"
            )
            row.stale_risk_share = record.get("stale_risk_share")
            row.monitor_profile_id = record.get("monitor_profile_id")
            row.monitor_observation_status = record.get("monitor_observation_status")
            session.add(row)
            session.flush()
            session.execute(
                delete(ResearchRunLiquidityCoverage).where(
                    ResearchRunLiquidityCoverage.run_id == row.run_id
                )
            )
            for item in record.get("liquidity_bucket_coverages", []):
                session.add(
                    ResearchRunLiquidityCoverage(
                        run_id=row.run_id,
                        bucket_key=item["bucket_key"],
                        bucket_label=item["bucket_label"],
                        full_universe_count=item["full_universe_count"],
                        execution_universe_count=item["execution_universe_count"],
                        full_universe_ratio=item["full_universe_ratio"],
                        execution_coverage_ratio=item["execution_coverage_ratio"],
                    )
                )
            if record.get("monitor_profile_id"):
                observations = record.get("microstructure_observations", [])
                trading_dates_by_market: dict[str, set[date]] = {}
                for item in observations:
                    market = item["market"]
                    trading_dates_by_market.setdefault(market, set()).add(
                        _coerce_date(item["trading_date"])
                    )
                if not trading_dates_by_market and record.get("market"):
                    trading_dates_by_market[record["market"]] = set()

                for market, trading_dates in trading_dates_by_market.items():
                    prune_stmt = (
                        delete(MicrostructureObservation)
                        .where(
                            MicrostructureObservation.monitor_profile_id
                            == record["monitor_profile_id"]
                        )
                        .where(MicrostructureObservation.market == market)
                    )
                    if trading_dates:
                        prune_stmt = prune_stmt.where(
                            MicrostructureObservation.trading_date.notin_(trading_dates)
                        )
                    session.execute(prune_stmt)

                for item in observations:
                    trading_date = _coerce_date(item["trading_date"])
                    stmt = (
                        select(MicrostructureObservation)
                        .where(
                            MicrostructureObservation.monitor_profile_id
                            == item["monitor_profile_id"]
                        )
                        .where(MicrostructureObservation.market == item["market"])
                        .where(MicrostructureObservation.trading_date == trading_date)
                    )
                    observation = session.execute(stmt).scalar_one_or_none()
                    if observation is None:
                        observation = MicrostructureObservation()
                        observation.monitor_profile_id = item["monitor_profile_id"]
                        observation.market = item["market"]
                        observation.trading_date = trading_date
                    observation.run_id = row.run_id
                    observation.full_universe_count = item["full_universe_count"]
                    observation.execution_universe_count = item[
                        "execution_universe_count"
                    ]
                    observation.execution_universe_ratio = item[
                        "execution_universe_ratio"
                    ]
                    observation.stale_mark_with_open_positions = item[
                        "stale_mark_with_open_positions"
                    ]
                    observation.liquidity_bucket_schema_version = item[
                        "liquidity_bucket_schema_version"
                    ]
                    observation.bucket_coverages_json = (
                        json_dumps(item["bucket_coverages"]) or "[]"
                    )
                    session.add(observation)
            session.commit()
            session.refresh(row)
            return _attach_liquidity_coverages(session, _run_row_to_dict(row))
    except Exception as exc:
        logger.exception(
            "Failed to persist research run record run_id=%s",
            record["run_id"],
        )
        raise DataAccessError("Failed to persist research run record.") from exc


def get_research_run_record(run_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, run_id)
            if row is not None:
                return _attach_liquidity_coverages(
                    session, _run_row_to_dict(row, include_artifacts=True)
                )
    except Exception as exc:
        logger.exception("Failed to load research run from DB run_id=%s", run_id)
        raise DataAccessError("Failed to load research run.") from exc

    raise DataNotFoundError(f"Research run '{run_id}' was not found.")


def list_research_run_records(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ResearchRun)
                .order_by(desc(ResearchRun.created_at), desc(ResearchRun.run_id))
                .limit(limit)
            )
            return [
                _attach_liquidity_coverages(
                    session, _run_row_to_dict(row, include_artifacts=False)
                )
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list research runs from DB")
        raise DataAccessError("Failed to list research runs.") from exc
