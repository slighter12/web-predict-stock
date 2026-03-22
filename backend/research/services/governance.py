from __future__ import annotations

from sqlalchemy import distinct, func, select

from backend.database import ResearchRun, ResearchRunLiquidityCoverage, SessionLocal
from backend.platform.errors import DataAccessError
from backend.shared.contracts.common import ACTIVE_TRADABILITY_CONTRACT_VERSION

_SUCCEEDED_STATUS = "succeeded"
_RUN_WINDOW = 20


def _is_active_contract_run(row: ResearchRun | None) -> bool:
    return (
        row is not None
        and row.tradability_contract_version == ACTIVE_TRADABILITY_CONTRACT_VERSION
    )


def _artifact(status: str, details: dict) -> dict:
    return {"status": status, "details": details}


def _metric(
    *,
    value: float | None,
    status: str,
    window: str,
    numerator: float | None = None,
    denominator: float | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "value": value,
        "status": status,
        "numerator": numerator,
        "denominator": denominator,
        "unit": None,
        "window": window,
        "details": details or {},
    }


def get_p3_phase_gate_summary() -> dict:
    try:
        with SessionLocal() as session:
            eligible_runs = (
                select(ResearchRun.run_id)
                .where(ResearchRun.status == _SUCCEEDED_STATUS)
                .where(
                    ResearchRun.tradability_contract_version
                    == ACTIVE_TRADABILITY_CONTRACT_VERSION
                )
            )
            latest_run = (
                session.execute(
                    select(ResearchRun)
                    .where(ResearchRun.status == _SUCCEEDED_STATUS)
                    .where(
                        ResearchRun.tradability_contract_version
                        == ACTIVE_TRADABILITY_CONTRACT_VERSION
                    )
                    .order_by(ResearchRun.created_at.desc(), ResearchRun.run_id.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            recent_runs = (
                session.execute(
                    select(ResearchRun)
                    .where(ResearchRun.status == _SUCCEEDED_STATUS)
                    .where(
                        ResearchRun.tradability_contract_version
                        == ACTIVE_TRADABILITY_CONTRACT_VERSION
                    )
                    .order_by(ResearchRun.created_at.desc(), ResearchRun.run_id.desc())
                    .limit(_RUN_WINDOW)
                )
                .scalars()
                .all()
            )
            latest_liquidity_coverage_count = 0
            if latest_run is not None:
                latest_liquidity_coverage_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(ResearchRunLiquidityCoverage)
                        .where(ResearchRunLiquidityCoverage.run_id == latest_run.run_id)
                    )
                    or 0
                )
            liquidity_coverage_run_count = (
                session.scalar(
                    select(func.count(distinct(ResearchRunLiquidityCoverage.run_id)))
                    .select_from(ResearchRunLiquidityCoverage)
                    .where(ResearchRunLiquidityCoverage.run_id.in_(eligible_runs))
                )
                or 0
            )
    except Exception as exc:
        raise DataAccessError("Failed to evaluate P3 phase gate summary.") from exc

    required_non_null_runs = 0
    for row in recent_runs:
        required_fields = [
            row.tradability_state,
            row.investability_screening_active,
            row.capacity_screening_active,
            row.missing_feature_policy_state,
            row.corporate_event_state,
            row.full_universe_count,
            row.execution_universe_count,
            row.execution_universe_ratio,
            row.liquidity_bucket_schema_version,
            row.stale_mark_days_with_open_positions,
            row.stale_risk_share,
        ]
        if all(value is not None for value in required_fields):
            required_non_null_runs += 1

    denominator = len(recent_runs)
    completeness_value = (
        float(required_non_null_runs / denominator) if denominator > 0 else None
    )
    completeness_status = "fail"
    if denominator >= _RUN_WINDOW and completeness_value == 1.0:
        completeness_status = "pass"
    elif denominator < _RUN_WINDOW:
        completeness_status = "insufficient_sample"

    latest_has_bucket_coverages = (
        _is_active_contract_run(latest_run)
        and latest_liquidity_coverage_count > 0
        and latest_run.liquidity_bucket_schema_version is not None
    )
    latest_has_summary = (
        _is_active_contract_run(latest_run)
        and latest_run.tradability_state is not None
        and latest_run.full_universe_count is not None
        and latest_run.execution_universe_count is not None
        and latest_run.execution_universe_ratio is not None
    )
    latest_has_missing_data_state = (
        _is_active_contract_run(latest_run)
        and latest_run.missing_feature_policy_state is not None
        and latest_run.corporate_event_state is not None
    )
    latest_has_stale = (
        _is_active_contract_run(latest_run)
        and latest_run.stale_mark_days_with_open_positions is not None
        and latest_run.stale_risk_share is not None
    )
    latest_has_capacity = (
        _is_active_contract_run(latest_run)
        and latest_run.capacity_screening_active is not None
        and (
            latest_run.capacity_screening_active is False
            or latest_run.capacity_screening_version is not None
        )
    )

    artifacts = {
        "lifecycle_aware_execution_universe": _artifact(
            "pass" if latest_has_summary else "fail",
            {
                "latest_run_id": latest_run.run_id if latest_run is not None else None,
                "tradability_state": latest_run.tradability_state
                if latest_run is not None
                else None,
                "execution_universe_count": latest_run.execution_universe_count
                if latest_run is not None
                else None,
            },
        ),
        "missing_data_states": _artifact(
            "pass" if latest_has_missing_data_state else "fail",
            {
                "latest_run_id": latest_run.run_id if latest_run is not None else None,
                "tradability_contract_version": latest_run.tradability_contract_version
                if latest_run is not None
                else None,
                "missing_feature_policy_state": latest_run.missing_feature_policy_state
                if latest_run is not None
                else None,
                "corporate_event_state": latest_run.corporate_event_state
                if latest_run is not None
                else None,
            },
        ),
        "stale_mark_flags": _artifact(
            "pass" if latest_has_stale else "fail",
            {
                "latest_run_id": latest_run.run_id if latest_run is not None else None,
                "tradability_contract_version": latest_run.tradability_contract_version
                if latest_run is not None
                else None,
                "stale_mark_days_with_open_positions": latest_run.stale_mark_days_with_open_positions
                if latest_run is not None
                else None,
                "stale_risk_share": latest_run.stale_risk_share
                if latest_run is not None
                else None,
            },
        ),
        "liquidity_and_capacity_labeling": _artifact(
            "pass" if latest_has_bucket_coverages and latest_has_capacity else "fail",
            {
                "latest_run_id": latest_run.run_id if latest_run is not None else None,
                "tradability_contract_version": latest_run.tradability_contract_version
                if latest_run is not None
                else None,
                "latest_liquidity_bucket_schema_version": latest_run.liquidity_bucket_schema_version
                if latest_run is not None
                else None,
                "latest_coverage_bucket_count": int(latest_liquidity_coverage_count),
                "coverage_run_count": int(liquidity_coverage_run_count),
                "capacity_screening_active": latest_run.capacity_screening_active
                if latest_run is not None
                else None,
                "capacity_screening_version": latest_run.capacity_screening_version
                if latest_run is not None
                else None,
            },
        ),
    }

    missing_reasons = [
        artifact_name
        for artifact_name, artifact in artifacts.items()
        if artifact["status"] != "pass"
    ]
    if completeness_status != "pass":
        missing_reasons.append("KPI-RESEARCH-004")

    overall_status = "pass"
    if completeness_status != "pass" or any(
        artifact["status"] != "pass" for artifact in artifacts.values()
    ):
        overall_status = "fail"

    return {
        "gate_id": "GATE-P3-001",
        "verification_gate_id": "GATE-VERIFICATION-001",
        "overall_status": overall_status,
        "metrics": {
            "KPI-RESEARCH-004": _metric(
                value=completeness_value,
                status=completeness_status,
                numerator=float(required_non_null_runs),
                denominator=float(denominator),
                window="rolling 20 runs",
                details={
                    "required_run_count": _RUN_WINDOW,
                    "passing_run_count": int(required_non_null_runs),
                    "tradability_contract_version": ACTIVE_TRADABILITY_CONTRACT_VERSION,
                },
            )
        },
        "artifacts": artifacts,
        "missing_reasons": missing_reasons,
    }
