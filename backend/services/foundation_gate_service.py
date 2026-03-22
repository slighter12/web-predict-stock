from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, func, select

from ..database import (
    AdaptiveSurfaceExclusion,
    AdaptiveTrainingRun,
    ClusterSnapshot,
    ExecutionFailureTaxonomy,
    ExecutionOrder,
    ExecutionOrderEvent,
    ExecutionPositionSnapshot,
    ExternalRawArchive,
    ExternalSignalAudit,
    FactorCatalog,
    FactorCatalogEntry,
    KillSwitchEvent,
    LiveRiskCheck,
    PeerFeatureRun,
    ResearchRun,
    SessionLocal,
)
from ..errors import DataAccessError

_P8_CONCENTRATION_METRIC_KEYS = (
    "weight_concentration",
    "max_position_weight",
    "top_5_weight_share",
    "top_10_weight_share",
    "herfindahl_index",
)
_P10_COMPLETE_STUB_LEDGER_EVENTS = {
    "submitted",
    "acknowledged",
    "filled",
    "position_readback",
}


def _artifact(status: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"status": status, "details": details}


def _metric(
    *,
    value: float | None,
    status: str,
    window: str,
    numerator: float | None = None,
    denominator: float | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "status": status,
        "numerator": numerator,
        "denominator": denominator,
        "unit": None,
        "window": window,
        "details": details or {},
    }


def _decode_metrics(row: ResearchRun) -> dict[str, Any]:
    if not row.metrics_json:
        return {}
    try:
        payload = json.loads(row.metrics_json)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_p7_phase_gate_summary() -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            latest_archive = (
                session.execute(
                    select(ExternalRawArchive)
                    .order_by(
                        desc(ExternalRawArchive.created_at), desc(ExternalRawArchive.id)
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            latest_audit = (
                session.execute(
                    select(ExternalSignalAudit)
                    .order_by(
                        desc(ExternalSignalAudit.created_at),
                        desc(ExternalSignalAudit.id),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            latest_catalog = (
                session.execute(
                    select(FactorCatalog)
                    .where(FactorCatalog.is_active.is_(True))
                    .order_by(desc(FactorCatalog.created_at), FactorCatalog.id)
                    .limit(1)
                )
                .scalars()
                .first()
            )
            entries = []
            if latest_catalog is not None:
                entries = (
                    session.execute(
                        select(FactorCatalogEntry).where(
                            FactorCatalogEntry.catalog_id == latest_catalog.id
                        )
                    )
                    .scalars()
                    .all()
                )
            eligible_entries = [entry for entry in entries if entry.scoring_eligible]
            complete_entries = [
                entry
                for entry in eligible_entries
                if entry.formula_definition
                and entry.lineage
                and entry.timing_semantics
                and entry.missing_value_policy
            ]
            factor_ratio = (
                float(len(complete_entries) / len(eligible_entries))
                if eligible_entries
                else None
            )
            leakage_value = (
                float(
                    latest_audit.undocumented_count / max(latest_audit.sample_size, 1)
                )
                if latest_audit and latest_audit.sample_size
                else None
            )
            latest_audit_result = (
                json.loads(latest_audit.result_json)
                if latest_audit and latest_audit.result_json
                else {}
            )
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P7 gate.") from exc

    factor_status = (
        "pass"
        if factor_ratio == 1.0
        else ("insufficient_sample" if factor_ratio is None else "fail")
    )
    leakage_status = (
        "pass"
        if leakage_value == 0.0
        else ("insufficient_sample" if leakage_value is None else "fail")
    )
    artifacts = {
        "external_signal_lineage": _artifact(
            "pass" if latest_archive is not None else "fail",
            {
                "latest_archive_id": latest_archive.id if latest_archive else None,
                "source_family": latest_archive.source_family
                if latest_archive
                else None,
                "record_count": latest_archive.record_count if latest_archive else 0,
            },
        ),
        "raw_external_archives": _artifact(
            "pass" if latest_archive is not None else "fail",
            {
                "latest_archive_id": latest_archive.id if latest_archive else None,
                "coverage_start": latest_archive.coverage_start
                if latest_archive
                else None,
                "coverage_end": latest_archive.coverage_end if latest_archive else None,
            },
        ),
        "timing_mapping": _artifact(
            "pass"
            if latest_audit is not None
            and latest_audit.sample_size > 0
            and latest_audit_result.get("exact_count") is not None
            and latest_audit_result.get("fallback_count") is not None
            and latest_audit_result.get("undocumented_ids") is not None
            and (
                int(latest_audit_result.get("exact_count", 0))
                + int(latest_audit_result.get("fallback_count", 0))
                + len(latest_audit_result.get("undocumented_ids", []))
                == latest_audit.sample_size
            )
            else "fail",
            {
                "sample_size": latest_audit.sample_size if latest_audit else 0,
                "exact_count": latest_audit_result.get("exact_count"),
                "fallback_count": latest_audit_result.get("fallback_count"),
                "undocumented_count": len(
                    latest_audit_result.get("undocumented_ids", [])
                ),
            },
        ),
        "factor_catalog": _artifact(
            "pass" if latest_catalog is not None and eligible_entries else "fail",
            {
                "factor_catalog_version": latest_catalog.id if latest_catalog else None,
                "eligible_factor_count": len(eligible_entries),
            },
        ),
    }
    overall_status = (
        "pass"
        if factor_status == "pass"
        and leakage_status == "pass"
        and all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    missing_reasons = [
        key for key, value in artifacts.items() if value["status"] != "pass"
    ]
    if factor_status != "pass":
        missing_reasons.append("KPI-FACTOR-001")
    if leakage_status != "pass":
        missing_reasons.append("KPI-EXT-003")
    return {
        "gate_id": "GATE-P7-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-EXT-003": _metric(
                value=leakage_value,
                status=leakage_status,
                numerator=float(
                    0
                    if leakage_value == 0
                    else latest_audit.undocumented_count
                    if latest_audit
                    else 0
                ),
                denominator=float(latest_audit.sample_size if latest_audit else 0),
                window="latest audited sample",
            ),
            "KPI-FACTOR-001": _metric(
                value=factor_ratio,
                status=factor_status,
                numerator=float(len(complete_entries)),
                denominator=float(len(eligible_entries)),
                window="active factor catalog",
            ),
        },
        "artifacts": artifacts,
        "missing_reasons": missing_reasons,
    }


def get_p8_phase_gate_summary() -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            latest_snapshot = (
                session.execute(
                    select(ClusterSnapshot)
                    .order_by(
                        desc(ClusterSnapshot.created_at), desc(ClusterSnapshot.id)
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            latest_peer_run = (
                session.execute(
                    select(PeerFeatureRun)
                    .order_by(desc(PeerFeatureRun.created_at), desc(PeerFeatureRun.id))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            comparable_runs = (
                session.execute(
                    select(ResearchRun)
                    .where(ResearchRun.status == "succeeded")
                    .where(ResearchRun.cluster_snapshot_version.is_not(None))
                    .where(ResearchRun.peer_policy_version.is_not(None))
                    .order_by(desc(ResearchRun.created_at), desc(ResearchRun.run_id))
                    .limit(50)
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P8 gate.") from exc

    comparable_count = len(comparable_runs)
    aligned_runs = [
        run
        for run in comparable_runs
        if run.price_basis_version
        and run.threshold_policy_version
        and run.comparison_eligibility
    ]
    reported_runs = [
        run
        for run in comparable_runs
        if (metrics := _decode_metrics(run)).get("turnover") is not None
        and any(metrics.get(key) is not None for key in _P8_CONCENTRATION_METRIC_KEYS)
    ]
    alignment_value = (
        float(len(aligned_runs) / comparable_count) if comparable_count else None
    )
    reporting_value = (
        float(len(reported_runs) / comparable_count) if comparable_count else None
    )
    alignment_status = (
        "pass"
        if comparable_count and len(aligned_runs) == comparable_count
        else ("insufficient_sample" if not comparable_count else "fail")
    )
    reporting_status = (
        "pass"
        if comparable_count and len(reported_runs) == comparable_count
        else ("insufficient_sample" if not comparable_count else "fail")
    )
    artifacts = {
        "point_in_time_cluster_snapshots": _artifact(
            "pass"
            if latest_snapshot is not None and latest_snapshot.status == "succeeded"
            else "fail",
            {
                "cluster_snapshot_version": latest_snapshot.snapshot_version
                if latest_snapshot
                else None,
                "symbol_count": latest_snapshot.symbol_count if latest_snapshot else 0,
                "trading_date": latest_snapshot.trading_date if latest_snapshot else None,
            },
        ),
        "peer_features": _artifact(
            "pass"
            if latest_peer_run is not None
            and latest_peer_run.status == "succeeded"
            and latest_peer_run.produced_feature_count > 0
            else "fail",
            {
                "peer_policy_version": latest_peer_run.peer_policy_version
                if latest_peer_run
                else None,
                "produced_feature_count": latest_peer_run.produced_feature_count
                if latest_peer_run
                else 0,
            },
        ),
        "peer_relative_comparison_outputs": _artifact(
            "pass" if comparable_count > 0 else "fail",
            {
                "comparable_run_count": comparable_count,
                "alignment_ready_run_count": len(aligned_runs),
                "reporting_ready_run_count": len(reported_runs),
            },
        ),
    }
    overall_status = (
        "pass"
        if alignment_status == "pass"
        and reporting_status == "pass"
        and all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P8-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-RESEARCH-002": _metric(
                value=alignment_value,
                status=alignment_status,
                numerator=float(len(aligned_runs)) if comparable_count else None,
                denominator=float(comparable_count) if comparable_count else None,
                window="latest 50 peer-enabled comparable runs",
            ),
            "KPI-RESEARCH-003": _metric(
                value=reporting_value,
                status=reporting_status,
                numerator=float(len(reported_runs)) if comparable_count else None,
                denominator=float(comparable_count) if comparable_count else None,
                window="latest 50 peer-enabled comparable runs",
            ),
        },
        "artifacts": artifacts,
        "missing_reasons": [
            key for key, value in artifacts.items() if value["status"] != "pass"
        ],
    }


def get_p9_phase_gate_summary() -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            simulation_order_rows = (
                session.execute(
                    select(ExecutionOrder)
                    .where(ExecutionOrder.route == "simulation_internal_v1")
                    .order_by(desc(ExecutionOrder.created_at), desc(ExecutionOrder.id))
                )
                .scalars()
                .all()
            )
            simulation_orders = len(simulation_order_rows)
            simulation_order_ids = [row.id for row in simulation_order_rows]
            event_rows = (
                session.execute(
                    select(ExecutionOrderEvent).where(
                        ExecutionOrderEvent.order_id.in_(simulation_order_ids)
                    )
                )
                .scalars()
                .all()
                if simulation_order_ids
                else []
            )
            readback_events = session.execute(
                select(func.count())
                .select_from(ExecutionOrderEvent)
                .join(ExecutionOrder, ExecutionOrder.id == ExecutionOrderEvent.order_id)
                .where(ExecutionOrder.route == "simulation_internal_v1")
                .where(ExecutionOrderEvent.event_type == "position_readback")
            ).scalar_one()
            positions = session.execute(
                select(func.count())
                .select_from(ExecutionPositionSnapshot)
                .where(ExecutionPositionSnapshot.route == "simulation_internal_v1")
            ).scalar_one()
            taxonomy_count = session.execute(
                select(func.count()).select_from(ExecutionFailureTaxonomy)
            ).scalar_one()
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P9 gate.") from exc

    event_types_by_order: dict[int, set[str]] = {}
    readback_telemetry_count = 0
    for row in event_rows:
        event_types_by_order.setdefault(row.order_id, set()).add(row.event_type)
        if row.event_type == "position_readback" and row.detail_json not in {"", "{}"}:
            readback_telemetry_count += 1
    order_history_count = len(
        [
            order_id
            for order_id, event_types in event_types_by_order.items()
            if "submitted" in event_types
            and "acknowledged" in event_types
            and ("filled" in event_types or "rejected" in event_types)
        ]
    )

    artifacts = {
        "simulation_adapter": _artifact(
            "pass" if simulation_orders > 0 else "fail",
            {"simulation_order_count": int(simulation_orders)},
        ),
        "fill_and_position_readback": _artifact(
            "pass" if readback_events > 0 and positions > 0 else "fail",
            {
                "readback_event_count": int(readback_events),
                "position_snapshot_count": int(positions),
            },
        ),
        "order_history_persistence": _artifact(
            "pass"
            if simulation_orders > 0 and order_history_count == simulation_orders
            else "fail",
            {
                "simulation_order_count": int(simulation_orders),
                "order_history_count": int(order_history_count),
                "event_row_count": len(event_rows),
            },
        ),
        "failure_taxonomy_registry": _artifact(
            "pass" if taxonomy_count > 0 else "fail",
            {"taxonomy_count": int(taxonomy_count)},
        ),
        "readback_telemetry_emission": _artifact(
            "pass"
            if readback_events > 0 and readback_telemetry_count == readback_events
            else "fail",
            {
                "readback_event_count": int(readback_events),
                "readback_telemetry_count": int(readback_telemetry_count),
            },
        ),
    }
    overall_status = (
        "pass"
        if all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P9-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {},
        "artifacts": artifacts,
        "missing_reasons": [
            key for key, value in artifacts.items() if value["status"] != "pass"
        ],
    }


def get_p10_phase_gate_summary() -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            live_orders = (
                session.execute(
                    select(ExecutionOrder)
                    .where(ExecutionOrder.route == "live_stub_v1")
                    .order_by(desc(ExecutionOrder.created_at), desc(ExecutionOrder.id))
                    .limit(20)
                )
                .scalars()
                .all()
            )
            if live_orders:
                order_ids = [order.id for order in live_orders]
                event_rows = (
                    session.execute(
                        select(ExecutionOrderEvent).where(
                            ExecutionOrderEvent.order_id.in_(order_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                risk_checks = (
                    session.execute(
                        select(LiveRiskCheck).where(
                            LiveRiskCheck.order_id.in_(order_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
            else:
                event_rows = []
                risk_checks = []
            kill_switch_count = session.execute(
                select(func.count()).select_from(KillSwitchEvent)
            ).scalar_one()
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P10 gate.") from exc

    order_count = len(live_orders)
    confirmed = len([order for order in live_orders if order.manual_confirmation])
    rejected_without_confirmation = len(
        [order for order in live_orders if not order.manual_confirmation]
    )
    risk_checked_orders = {check.order_id for check in risk_checks}
    manual_value = float(confirmed / order_count) if order_count else None
    risk_value = float(len(risk_checked_orders) / order_count) if order_count else None
    unconfirmed_value = (
        float(rejected_without_confirmation / order_count) if order_count else None
    )
    manual_status = (
        "pass"
        if order_count and manual_value == 1.0
        else ("insufficient_sample" if not order_count else "fail")
    )
    risk_status = (
        "pass"
        if order_count and risk_value == 1.0
        else ("insufficient_sample" if not order_count else "fail")
    )
    unconfirmed_status = (
        "pass"
        if order_count and rejected_without_confirmation == 0
        else ("insufficient_sample" if not order_count else "fail")
    )
    event_types_by_order: dict[int, set[str]] = {}
    for row in event_rows:
        event_types_by_order.setdefault(row.order_id, set()).add(row.event_type)
    broker_logged_orders = [
        order
        for order in live_orders
        if (
            ("rejected" in event_types_by_order.get(order.id, set()))
            if order.status == "rejected"
            else _P10_COMPLETE_STUB_LEDGER_EVENTS.issubset(
                event_types_by_order.get(order.id, set())
            )
        )
    ]
    artifacts = {
        "manual_confirmation_gate": _artifact(
            "pass" if manual_status == "pass" else "fail",
            {"live_order_count": order_count, "confirmed_count": confirmed},
        ),
        "risk_checks": _artifact(
            "pass" if risk_status == "pass" else "fail",
            {"risk_check_count": len(risk_checked_orders)},
        ),
        "kill_switch": _artifact(
            "pass" if kill_switch_count > 0 else "fail",
            {"kill_switch_event_count": int(kill_switch_count)},
        ),
        "broker_order_logging": _artifact(
            "pass"
            if order_count and len(broker_logged_orders) == order_count
            else "fail",
            {
                "logged_order_count": len(broker_logged_orders),
                "live_order_count": order_count,
            },
        ),
    }
    overall_status = (
        "pass"
        if manual_status == "pass"
        and risk_status == "pass"
        and unconfirmed_status == "pass"
        and all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P10-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-LIVE-001": _metric(
                value=manual_value,
                status=manual_status,
                numerator=float(confirmed),
                denominator=float(order_count),
                window="rolling 20 live-order events",
            ),
            "KPI-LIVE-002": _metric(
                value=risk_value,
                status=risk_status,
                numerator=float(len(risk_checked_orders)),
                denominator=float(order_count),
                window="rolling 20 live-order events",
            ),
            "KPI-LIVE-003": _metric(
                value=unconfirmed_value,
                status=unconfirmed_status,
                numerator=float(rejected_without_confirmation),
                denominator=float(order_count),
                window="rolling 20 live-order events",
            ),
        },
        "artifacts": artifacts,
        "missing_reasons": [
            key for key, value in artifacts.items() if value["status"] != "pass"
        ],
    }


def get_p11_phase_gate_summary() -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            adaptive_runs = (
                session.execute(
                    select(ResearchRun)
                    .where(ResearchRun.adaptive_mode.is_not(None))
                    .where(ResearchRun.adaptive_mode != "off")
                    .order_by(desc(ResearchRun.created_at), desc(ResearchRun.run_id))
                    .limit(50)
                )
                .scalars()
                .all()
            )
            run_ids = [run.run_id for run in adaptive_runs]
            exclusions = (
                session.execute(
                    select(AdaptiveSurfaceExclusion).where(
                        AdaptiveSurfaceExclusion.run_id.in_(run_ids)
                    )
                )
                .scalars()
                .all()
                if run_ids
                else []
            )
            trainings = (
                session.execute(
                    select(AdaptiveTrainingRun)
                    .order_by(
                        desc(AdaptiveTrainingRun.created_at),
                        desc(AdaptiveTrainingRun.id),
                    )
                    .limit(50)
                )
                .scalars()
                .all()
            )
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P11 gate.") from exc

    total = len(adaptive_runs)
    opt_in_count = len(
        [
            run
            for run in adaptive_runs
            if run.adaptive_profile_id
            and run.reward_definition_version
            and run.state_definition_version
            and run.rollout_control_version
        ]
    )
    excluded_run_ids = {row.run_id for row in exclusions}
    contamination_count = len(
        [
            run
            for run in adaptive_runs
            if run.run_id not in excluded_run_ids
            and (
                (
                    run.comparison_eligibility is not None
                    and run.comparison_eligibility != "unresolved_event_quarantine"
                )
                or run.tradability_state == "execution_ready"
            )
        ]
    )
    rollout_count = len(
        [
            run
            for run in adaptive_runs
            if run.rollout_control_version and run.adaptive_contract_version
        ]
    )
    opt_in_value = float(opt_in_count / total) if total else None
    contamination_value = float(contamination_count / total) if total else None
    rollout_value = float(rollout_count / total) if total else None
    status_for_ratio = lambda value, total_count: (
        "pass"
        if total_count and value == 1.0
        else ("insufficient_sample" if not total_count else "fail")
    )
    opt_in_status = status_for_ratio(opt_in_value, total)
    rollout_status = status_for_ratio(rollout_value, total)
    contamination_status = (
        "pass"
        if total and contamination_count == 0
        else ("insufficient_sample" if not total else "fail")
    )
    artifacts = {
        "isolated_adaptive_workflow": _artifact(
            "pass" if trainings else "fail",
            {"adaptive_training_run_count": len(trainings)},
        ),
        "reward_and_state_definitions": _artifact(
            "pass" if opt_in_status == "pass" else "fail",
            {"adaptive_run_count": total, "opt_in_count": opt_in_count},
        ),
        "non_default_rollout_controls": _artifact(
            "pass" if rollout_status == "pass" else "fail",
            {"rollout_control_count": rollout_count},
        ),
    }
    overall_status = (
        "pass"
        if opt_in_status == "pass"
        and contamination_status == "pass"
        and rollout_status == "pass"
        and all(item["status"] == "pass" for item in artifacts.values())
        else "fail"
    )
    return {
        "gate_id": "GATE-P11-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-ADAPT-001": _metric(
                value=opt_in_value,
                status=opt_in_status,
                numerator=float(opt_in_count),
                denominator=float(total),
                window="rolling 50 adaptive runs or full history when fewer",
            ),
            "KPI-ADAPT-002": _metric(
                value=contamination_value,
                status=contamination_status,
                numerator=float(contamination_count),
                denominator=float(total),
                window="rolling 50 adaptive runs or full history when fewer",
            ),
            "KPI-ADAPT-003": _metric(
                value=rollout_value,
                status=rollout_status,
                numerator=float(rollout_count),
                denominator=float(total),
                window="rolling 50 adaptive runs or full history when fewer",
            ),
        },
        "artifacts": artifacts,
        "missing_reasons": [
            key for key, value in artifacts.items() if value["status"] != "pass"
        ],
    }
