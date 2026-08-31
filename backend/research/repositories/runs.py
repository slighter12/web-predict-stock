from __future__ import annotations

import logging
from contextlib import nullcontext
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, desc, select

from backend.database import (
    MicrostructureObservation,
    ResearchRun,
    ResearchRunLiquidityCoverage,
    SessionLocal,
)
from backend.platform.db.repository_helpers import (
    clone_payload,
    json_dumps,
    json_loads,
    normalize_created_at,
)
from backend.platform.errors import DataAccessError, DataNotFoundError
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)

_PROSPECTIVE_COHORT_BATCH_SIZE = 500
_MISSING_OR_INVALID_JSON = object()
# Compatibility envelope until ResearchRun gains a dedicated field and a
# backfill migration for the feature registry version.
_RESULT_METADATA_KEY = "_result_metadata"
_REQUEST_PAYLOAD_ABSENT_KEY = "request_payload_absent"


def _split_persisted_request_payload(
    payload: Any,
) -> tuple[Any, dict[str, Any]]:
    """Separate internal result metadata from the user request projection."""
    if not isinstance(payload, dict):
        return payload, {}

    request_payload = dict(payload)
    result_metadata = request_payload.pop(_RESULT_METADATA_KEY, None)
    if not isinstance(result_metadata, dict):
        result_metadata = {}
    else:
        result_metadata = dict(result_metadata)

    request_payload_absent = (
        result_metadata.pop(_REQUEST_PAYLOAD_ABSENT_KEY, False) is True
    )
    legacy_version = request_payload.pop("feature_registry_version", None)
    if (
        "feature_registry_version" not in result_metadata
        and legacy_version is not None
    ):
        result_metadata["feature_registry_version"] = legacy_version
    if request_payload_absent and not request_payload:
        return None, result_metadata
    return request_payload, result_metadata


def _build_persisted_request_payload(
    payload: Any,
    *,
    feature_registry_version: str | None,
) -> Any:
    """Persist request data with result metadata in the existing JSON column."""
    if not isinstance(payload, dict):
        if payload is None and feature_registry_version is not None:
            return {
                _RESULT_METADATA_KEY: {
                    "feature_registry_version": feature_registry_version,
                    _REQUEST_PAYLOAD_ABSENT_KEY: True,
                }
            }
        return payload

    persisted = dict(payload)
    result_metadata = persisted.get(_RESULT_METADATA_KEY)
    if not isinstance(result_metadata, dict):
        result_metadata = {}
    if feature_registry_version is not None:
        result_metadata = {
            **result_metadata,
            "feature_registry_version": feature_registry_version,
        }
    if result_metadata:
        persisted[_RESULT_METADATA_KEY] = result_metadata
    return persisted


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


def _run_row_to_snapshot(
    row: ResearchRun, *, include_artifacts: bool = True
) -> dict[str, Any]:
    validation_outcome = json_loads(row.validation_outcome_json, None)
    model_diagnostics = json_loads(row.model_diagnostics_json, None)
    persisted_request_payload = json_loads(row.request_payload_json, None)
    request_payload, result_metadata = _split_persisted_request_payload(
        persisted_request_payload
    )
    strategy_payload = (
        request_payload.get("strategy")
        if isinstance(request_payload, dict)
        else None
    )
    threshold_mode = (
        strategy_payload.get("threshold_mode", "static")
        if isinstance(strategy_payload, dict)
        else "static"
    )
    effective_strategy = None
    dynamic_top_n = (
        row.effective_top_n
        if row.effective_top_n is not None
        else strategy_payload.get("top_n")
        if isinstance(strategy_payload, dict)
        else None
    )
    dynamic_threshold_policy = (
        strategy_payload.get("dynamic_threshold_policy")
        if isinstance(strategy_payload, dict)
        else None
    )
    # Static legacy snapshots retain the optional-column fallback; dynamic
    # snapshots require both persisted values before projection can validate it.
    if threshold_mode == "dynamic":
        if dynamic_top_n is not None and dynamic_threshold_policy is not None:
            effective_strategy = {
                "threshold": None,
                "top_n": dynamic_top_n,
                "threshold_mode": "dynamic",
                "dynamic_threshold_policy": dynamic_threshold_policy,
            }
    elif row.effective_threshold is not None and row.effective_top_n is not None:
        effective_strategy = {
            "threshold": row.effective_threshold,
            "top_n": row.effective_top_n,
        }
    metrics = json_loads(row.metrics_json, None)
    equity_curve = json_loads(row.equity_curve_json, _MISSING_OR_INVALID_JSON)
    signals = json_loads(row.signals_json, _MISSING_OR_INVALID_JSON)
    scoring_factor_ids = json_loads(row.scoring_factor_ids_json, [])
    parsed_baselines = json_loads(row.baselines_json, None)
    baselines = parsed_baselines if isinstance(parsed_baselines, dict) else {}
    warnings = json_loads(row.warnings_json, [])
    feature_registry_version = result_metadata.get("feature_registry_version")
    payload = {
        "run_id": row.run_id,
        "request_id": row.request_id,
        "status": row.status,
        "feature_registry_version": feature_registry_version,
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
        "request_payload": request_payload,
        "metrics": metrics,
        "equity_curve": (
            [] if equity_curve is _MISSING_OR_INVALID_JSON else equity_curve
        )
        if include_artifacts
        else [],
        "signals": ([] if signals is _MISSING_OR_INVALID_JSON else signals)
        if include_artifacts
        else [],
        "baselines": baselines,
        "warnings": warnings,
        "factor_catalog_version": row.factor_catalog_version,
        "scoring_factor_ids": scoring_factor_ids,
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
        "_raw_model_diagnostics": model_diagnostics,
        "_artifact_presence": {
            "metrics": isinstance(metrics, dict),
            "model_diagnostics": False,
            "equity_curve": row.equity_curve_json is not None
            and isinstance(equity_curve, list),
            "signals": row.signals_json is not None and isinstance(signals, list),
            "validation": False,
            "baselines": isinstance(parsed_baselines, dict),
        },
        "_version_pack_values": {
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
            "comparison_review_matrix_version": row.comparison_review_matrix_version,
            "scheduled_review_cadence": row.scheduled_review_cadence,
            "model_family": row.model_family,
            "training_output_contract_version": row.training_output_contract_version,
            "adoption_comparison_policy_version": row.adoption_comparison_policy_version,
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
            "scoring_factor_ids": scoring_factor_ids,
        },
    }
    return payload


def _attach_liquidity_coverages(
    session: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    coverages_by_run_id = _load_liquidity_coverages(
        session,
        [payload["run_id"]],
    )
    payload["liquidity_bucket_coverages"] = coverages_by_run_id.get(
        payload["run_id"], []
    )
    return payload


def _load_liquidity_coverages(
    session: Any,
    run_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not run_ids:
        return {}

    stmt = (
        select(ResearchRunLiquidityCoverage)
        .where(ResearchRunLiquidityCoverage.run_id.in_(run_ids))
        .order_by(
            ResearchRunLiquidityCoverage.run_id.asc(),
            ResearchRunLiquidityCoverage.bucket_key.asc(),
        )
    )
    coverages_by_run_id: dict[str, list[dict[str, Any]]] = {}
    for row in session.execute(stmt).scalars().all():
        coverages_by_run_id.setdefault(row.run_id, []).append(
            {
                "bucket_key": row.bucket_key,
                "bucket_label": row.bucket_label,
                "full_universe_count": row.full_universe_count,
                "execution_universe_count": row.execution_universe_count,
                "full_universe_ratio": row.full_universe_ratio,
                "execution_coverage_ratio": row.execution_coverage_ratio,
            }
        )
    return coverages_by_run_id


def persist_research_run_record(
    payload: dict[str, Any], *, session: Any | None = None, commit: bool = True
) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("symbols", [])
    record.setdefault("warnings", [])
    record.setdefault("created_at", utc_now())

    try:
        session_context = SessionLocal() if session is None else nullcontext(session)
        with session_context as session:
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
            row.request_payload_json = json_dumps(
                _build_persisted_request_payload(
                    record.get("request_payload"),
                    feature_registry_version=record.get("feature_registry_version"),
                )
            )
            row.metrics_json = json_dumps(record.get("metrics"))
            row.equity_curve_json = json_dumps(record.get("equity_curve", []))
            row.signals_json = json_dumps(record.get("signals", []))
            row.model_diagnostics_json = json_dumps(record.get("model_diagnostics"))
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
            if commit:
                session.commit()
                session.refresh(row)
            return _attach_liquidity_coverages(session, _run_row_to_snapshot(row))
    except Exception as exc:
        logger.exception(
            "Failed to persist research run record run_id=%s",
            record["run_id"],
        )
        raise DataAccessError("Failed to persist research run record.") from exc


def get_research_run_request_payload(run_id: str) -> dict[str, Any] | None:
    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, run_id)
            if row is not None:
                payload = json_loads(row.request_payload_json, None)
                request_payload, _ = _split_persisted_request_payload(payload)
                return request_payload
    except Exception as exc:
        logger.exception(
            "Failed to load research run request payload run_id=%s",
            run_id,
        )
        raise DataAccessError("Failed to load research run request payload.") from exc
    raise DataNotFoundError(f"Research run '{run_id}' was not found.")


def get_research_run_snapshot(run_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(ResearchRun, run_id)
            if row is not None:
                return _attach_liquidity_coverages(
                    session, _run_row_to_snapshot(row, include_artifacts=True)
                )
    except Exception as exc:
        logger.exception("Failed to load research run from DB run_id=%s", run_id)
        raise DataAccessError("Failed to load research run.") from exc

    raise DataNotFoundError(f"Research run '{run_id}' was not found.")


def list_prospective_cohort_run_snapshots(
    cohort_id: str,
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            candidate_stmt = (
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
            )
            candidate_result = session.execute(
                candidate_stmt.execution_options(
                    yield_per=_PROSPECTIVE_COHORT_BATCH_SIZE
                )
            )
            candidate_ids: list[str] = []
            for candidate_rows in candidate_result.partitions(
                _PROSPECTIVE_COHORT_BATCH_SIZE
            ):
                for run_id, request_payload_json in candidate_rows:
                    request_payload = json_loads(request_payload_json, None)
                    evidence = (
                        request_payload.get("prospective_evidence")
                        if isinstance(request_payload, dict)
                        else None
                    )
                    if (
                        not isinstance(evidence, dict)
                        or evidence.get("cohort_id") != cohort_id
                    ):
                        continue
                    candidate_ids.append(run_id)

            snapshots: list[dict[str, Any]] = []
            for start in range(
                0,
                len(candidate_ids),
                _PROSPECTIVE_COHORT_BATCH_SIZE,
            ):
                candidate_batch = candidate_ids[
                    start : start + _PROSPECTIVE_COHORT_BATCH_SIZE
                ]
                row_stmt = (
                    select(ResearchRun)
                    .where(ResearchRun.run_id.in_(candidate_batch))
                    .order_by(ResearchRun.created_at.asc(), ResearchRun.run_id.asc())
                )
                rows = session.execute(row_stmt).scalars().all()
                coverages_by_run_id = _load_liquidity_coverages(
                    session,
                    [row.run_id for row in rows],
                )
                for row in rows:
                    snapshot = _run_row_to_snapshot(row, include_artifacts=True)
                    snapshot["liquidity_bucket_coverages"] = (
                        coverages_by_run_id.get(row.run_id, [])
                    )
                    snapshots.append(snapshot)

            snapshots.sort(
                key=lambda snapshot: (snapshot["created_at"], snapshot["run_id"])
            )
            return snapshots
    except Exception as exc:
        logger.exception(
            "Failed to list prospective cohort runs cohort_id=%s",
            cohort_id,
        )
        raise DataAccessError("Failed to list prospective cohort runs.") from exc


def list_research_run_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ResearchRun)
                .order_by(desc(ResearchRun.created_at), desc(ResearchRun.run_id))
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            coverages_by_run_id = _load_liquidity_coverages(
                session,
                [row.run_id for row in rows],
            )
            snapshots = []
            for row in rows:
                snapshot = _run_row_to_snapshot(row, include_artifacts=False)
                snapshot["liquidity_bucket_coverages"] = coverages_by_run_id.get(
                    row.run_id,
                    [],
                )
                snapshots.append(snapshot)
            return snapshots
    except Exception as exc:
        logger.exception("Failed to list research runs from DB")
        raise DataAccessError("Failed to list research runs.") from exc
