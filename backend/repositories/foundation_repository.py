from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from ..database import (
    AdaptiveProfile,
    AdaptiveRolloutControl,
    AdaptiveSurfaceExclusion,
    AdaptiveTrainingRun,
    ClusterMembership,
    ClusterSnapshot,
    ExecutionFailureTaxonomy,
    ExecutionFillEvent,
    ExecutionOrder,
    ExecutionOrderEvent,
    ExecutionPositionSnapshot,
    ExternalRawArchive,
    ExternalSignalAudit,
    ExternalSignalRecord,
    FactorCatalog,
    FactorCatalogEntry,
    FactorMaterialization,
    FactorUsabilityObservation,
    KillSwitchEvent,
    LiveControlProfile,
    LiveRiskCheck,
    PeerComparisonOverlay,
    PeerFeatureRun,
    SessionLocal,
    SimulationProfile,
)
from ..errors import DataAccessError, DataNotFoundError
from ._shared import json_dumps, json_loads, normalize_created_at

logger = logging.getLogger(__name__)


def _external_archive_row_to_dict(row: ExternalRawArchive) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_family": row.source_family,
        "market": row.market,
        "coverage_start": row.coverage_start,
        "coverage_end": row.coverage_end,
        "record_count": row.record_count,
        "payload_body": row.payload_body,
        "notes": row.notes,
        "created_at": normalize_created_at(row.created_at),
    }


def _external_signal_row_to_dict(row: ExternalSignalRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "archive_id": row.archive_id,
        "source_family": row.source_family,
        "source_record_type": row.source_record_type,
        "symbol": row.symbol,
        "market": row.market,
        "effective_date": row.effective_date,
        "available_at": row.available_at,
        "availability_mode": row.availability_mode,
        "lineage_version": row.lineage_version,
        "detail": json_loads(row.detail_json, {}),
        "created_at": normalize_created_at(row.created_at),
    }


def _audit_row_to_dict(row: ExternalSignalAudit) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_family": row.source_family,
        "market": row.market,
        "audit_window_start": row.audit_window_start,
        "audit_window_end": row.audit_window_end,
        "sample_size": row.sample_size,
        "fallback_sample_size": row.fallback_sample_size,
        "undocumented_count": row.undocumented_count,
        "draw_rule_version": row.draw_rule_version,
        "result": json_loads(row.result_json, {}),
        "created_at": normalize_created_at(row.created_at),
    }


def _factor_entry_row_to_dict(row: FactorCatalogEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "catalog_id": row.catalog_id,
        "factor_id": row.factor_id,
        "display_name": row.display_name,
        "formula_definition": row.formula_definition,
        "lineage": row.lineage,
        "timing_semantics": row.timing_semantics,
        "missing_value_policy": row.missing_value_policy,
        "scoring_eligible": row.scoring_eligible,
        "created_at": normalize_created_at(row.created_at),
    }


def _factor_catalog_row_to_dict(
    row: FactorCatalog, entries: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "source_family": row.source_family,
        "lineage_version": row.lineage_version,
        "minimum_coverage_ratio": row.minimum_coverage_ratio,
        "is_active": row.is_active,
        "notes": row.notes,
        "created_at": normalize_created_at(row.created_at),
        "entries": entries or [],
    }


def _factor_materialization_row_to_dict(row: FactorMaterialization) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "catalog_id": row.catalog_id,
        "factor_id": row.factor_id,
        "symbol": row.symbol,
        "market": row.market,
        "trading_date": row.trading_date,
        "value": row.value,
        "source_available_at": row.source_available_at,
        "factor_available_ts": row.factor_available_ts,
        "availability_mode": row.availability_mode,
        "created_at": normalize_created_at(row.created_at),
    }


def _cluster_membership_row_to_dict(row: ClusterMembership) -> dict[str, Any]:
    return {
        "id": row.id,
        "snapshot_id": row.snapshot_id,
        "symbol": row.symbol,
        "cluster_label": row.cluster_label,
        "distance_to_centroid": row.distance_to_centroid,
        "created_at": normalize_created_at(row.created_at),
    }


def _cluster_snapshot_row_to_dict(
    row: ClusterSnapshot, memberships: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "id": row.id,
        "snapshot_version": row.snapshot_version,
        "run_id": row.run_id,
        "factor_catalog_version": row.factor_catalog_version,
        "market": row.market,
        "trading_date": row.trading_date,
        "cluster_count": row.cluster_count,
        "symbol_count": row.symbol_count,
        "status": row.status,
        "notes": row.notes,
        "memberships": memberships or [],
        "created_at": normalize_created_at(row.created_at),
    }


def _peer_overlay_row_to_dict(row: PeerComparisonOverlay) -> dict[str, Any]:
    return {
        "id": row.id,
        "peer_feature_run_id": row.peer_feature_run_id,
        "symbol": row.symbol,
        "peer_symbol_count": row.peer_symbol_count,
        "peer_feature_value": row.peer_feature_value,
        "detail": json_loads(row.detail_json, {}),
        "created_at": normalize_created_at(row.created_at),
    }


def _peer_feature_run_row_to_dict(
    row: PeerFeatureRun, overlays: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "snapshot_id": row.snapshot_id,
        "peer_policy_version": row.peer_policy_version,
        "market": row.market,
        "trading_date": row.trading_date,
        "status": row.status,
        "produced_feature_count": row.produced_feature_count,
        "warning_count": row.warning_count,
        "warnings": json_loads(row.warning_json, []),
        "overlays": overlays or [],
        "created_at": normalize_created_at(row.created_at),
    }


def _execution_event_row_to_dict(row: ExecutionOrderEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "event_type": row.event_type,
        "event_ts": row.event_ts,
        "detail": json_loads(row.detail_json, {}),
        "created_at": normalize_created_at(row.created_at),
    }


def _execution_fill_row_to_dict(row: ExecutionFillEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "fill_ts": row.fill_ts,
        "fill_price": row.fill_price,
        "quantity": row.quantity,
        "slippage_bps": row.slippage_bps,
        "created_at": normalize_created_at(row.created_at),
    }


def _execution_position_row_to_dict(row: ExecutionPositionSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "run_id": row.run_id,
        "route": row.route,
        "market": row.market,
        "symbol": row.symbol,
        "quantity": row.quantity,
        "avg_price": row.avg_price,
        "snapshot_ts": row.snapshot_ts,
        "created_at": normalize_created_at(row.created_at),
    }


def _risk_check_row_to_dict(row: LiveRiskCheck) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "status": row.status,
        "detail": json_loads(row.detail_json, {}),
        "checked_at": row.checked_at,
        "created_at": normalize_created_at(row.created_at),
    }


def _execution_order_row_to_dict(
    row: ExecutionOrder,
    *,
    events: list[dict[str, Any]] | None = None,
    fills: list[dict[str, Any]] | None = None,
    positions: list[dict[str, Any]] | None = None,
    risk_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "route": row.route,
        "market": row.market,
        "symbol": row.symbol,
        "side": row.side,
        "quantity": row.quantity,
        "requested_price": row.requested_price,
        "status": row.status,
        "simulation_profile_id": row.simulation_profile_id,
        "live_control_profile_id": row.live_control_profile_id,
        "failure_code": row.failure_code,
        "manual_confirmation": row.manual_confirmation,
        "rejection_reason": row.rejection_reason,
        "submitted_at": row.submitted_at,
        "acknowledged_at": row.acknowledged_at,
        "created_at": normalize_created_at(row.created_at),
        "events": events or [],
        "fills": fills or [],
        "positions": positions or [],
        "risk_checks": risk_checks or [],
    }


def _kill_switch_row_to_dict(row: KillSwitchEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "scope_type": row.scope_type,
        "market": row.market,
        "is_enabled": row.is_enabled,
        "reason": row.reason,
        "created_at": normalize_created_at(row.created_at),
    }


def _adaptive_profile_row_to_dict(
    row: AdaptiveProfile,
    rollout_control: AdaptiveRolloutControl | None = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "reward_definition_version": row.reward_definition_version,
        "state_definition_version": row.state_definition_version,
        "notes": row.notes,
        "rollout_control_version": rollout_control.rollout_control_version
        if rollout_control
        else None,
        "rollout_mode": rollout_control.mode if rollout_control else None,
        "rollout_detail": json_loads(rollout_control.detail_json, {})
        if rollout_control
        else {},
        "created_at": normalize_created_at(row.created_at),
    }


def _adaptive_training_run_row_to_dict(row: AdaptiveTrainingRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "profile_id": row.profile_id,
        "run_id": row.run_id,
        "market": row.market,
        "adaptive_mode": row.adaptive_mode,
        "reward_definition_version": row.reward_definition_version,
        "state_definition_version": row.state_definition_version,
        "rollout_control_version": row.rollout_control_version,
        "status": row.status,
        "dataset_summary": json_loads(row.dataset_summary_json, {}),
        "artifact_registry": json_loads(row.artifact_registry_json, {}),
        "validation_error": row.validation_error,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_external_signal_ingestion(
    archive_payload: dict[str, Any], signal_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            archive = ExternalRawArchive(**archive_payload)
            session.add(archive)
            session.flush()
            for payload in signal_rows:
                session.add(
                    ExternalSignalRecord(
                        archive_id=archive.id,
                        source_family=payload["source_family"],
                        source_record_type=payload["source_record_type"],
                        symbol=payload["symbol"],
                        market=payload["market"],
                        effective_date=payload["effective_date"],
                        available_at=payload.get("available_at"),
                        availability_mode=payload["availability_mode"],
                        lineage_version=payload["lineage_version"],
                        detail_json=json_dumps(payload.get("detail", {})) or "{}",
                    )
                )
            archive.record_count = len(signal_rows)
            session.commit()
            session.refresh(archive)
            return _external_archive_row_to_dict(archive)
    except Exception as exc:
        logger.exception("Failed to persist external signal ingestion")
        raise DataAccessError("Failed to persist external signal ingestion.") from exc


def list_external_signal_records(limit: int = 200) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ExternalSignalRecord)
                .order_by(
                    desc(ExternalSignalRecord.effective_date),
                    desc(ExternalSignalRecord.id),
                )
                .limit(limit)
            )
            return [
                _external_signal_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list external signal records")
        raise DataAccessError("Failed to list external signal records.") from exc


def list_external_signal_records_for_window(
    *,
    source_family: str,
    market: str,
    window_start: date,
    window_end: date,
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ExternalSignalRecord)
                .where(ExternalSignalRecord.source_family == source_family)
                .where(ExternalSignalRecord.market == market)
                .where(ExternalSignalRecord.effective_date >= window_start)
                .where(ExternalSignalRecord.effective_date <= window_end)
                .order_by(
                    ExternalSignalRecord.effective_date.asc(),
                    ExternalSignalRecord.id.asc(),
                )
            )
            return [
                _external_signal_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception(
            "Failed to list external signal records for audit window source_family=%s market=%s",
            source_family,
            market,
        )
        raise DataAccessError(
            "Failed to list external signal records for audit window."
        ) from exc


def persist_external_signal_audit(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = ExternalSignalAudit(
                source_family=payload["source_family"],
                market=payload["market"],
                audit_window_start=payload["audit_window_start"],
                audit_window_end=payload["audit_window_end"],
                sample_size=payload["sample_size"],
                fallback_sample_size=payload["fallback_sample_size"],
                undocumented_count=payload["undocumented_count"],
                draw_rule_version=payload["draw_rule_version"],
                result_json=json_dumps(payload.get("result", {})) or "{}",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _audit_row_to_dict(row)
    except Exception as exc:
        logger.exception("Failed to persist external signal audit")
        raise DataAccessError("Failed to persist external signal audit.") from exc


def list_external_signal_audits(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ExternalSignalAudit)
                .order_by(
                    desc(ExternalSignalAudit.created_at), desc(ExternalSignalAudit.id)
                )
                .limit(limit)
            )
            return [
                _audit_row_to_dict(row) for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list external signal audits")
        raise DataAccessError("Failed to list external signal audits.") from exc


def persist_factor_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(FactorCatalog, payload["id"]) or FactorCatalog(
                id=payload["id"]
            )
            row.market = payload["market"]
            row.source_family = payload["source_family"]
            row.lineage_version = payload["lineage_version"]
            row.minimum_coverage_ratio = payload["minimum_coverage_ratio"]
            row.is_active = payload["is_active"]
            row.notes = payload.get("notes")
            session.add(row)
            session.flush()
            session.query(FactorCatalogEntry).filter(
                FactorCatalogEntry.catalog_id == row.id
            ).delete()
            for entry in payload.get("entries", []):
                session.add(
                    FactorCatalogEntry(
                        catalog_id=row.id,
                        factor_id=entry["factor_id"],
                        display_name=entry["display_name"],
                        formula_definition=entry["formula_definition"],
                        lineage=entry["lineage"],
                        timing_semantics=entry["timing_semantics"],
                        missing_value_policy=entry["missing_value_policy"],
                        scoring_eligible=entry["scoring_eligible"],
                    )
                )
            session.commit()
            session.refresh(row)
            entries = [
                _factor_entry_row_to_dict(entry)
                for entry in session.execute(
                    select(FactorCatalogEntry)
                    .where(FactorCatalogEntry.catalog_id == row.id)
                    .order_by(FactorCatalogEntry.factor_id.asc())
                )
                .scalars()
                .all()
            ]
            return _factor_catalog_row_to_dict(row, entries)
    except Exception as exc:
        logger.exception(
            "Failed to persist factor catalog catalog_id=%s", payload["id"]
        )
        raise DataAccessError("Failed to persist factor catalog.") from exc


def get_factor_catalog(catalog_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(FactorCatalog, catalog_id)
            if row is None:
                raise DataNotFoundError(f"Factor catalog '{catalog_id}' was not found.")
            entries = [
                _factor_entry_row_to_dict(entry)
                for entry in session.execute(
                    select(FactorCatalogEntry)
                    .where(FactorCatalogEntry.catalog_id == row.id)
                    .order_by(FactorCatalogEntry.factor_id.asc())
                )
                .scalars()
                .all()
            ]
            return _factor_catalog_row_to_dict(row, entries)
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load factor catalog catalog_id=%s", catalog_id)
        raise DataAccessError("Failed to load factor catalog.") from exc


def list_factor_catalogs(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(FactorCatalog)
                .order_by(desc(FactorCatalog.created_at), FactorCatalog.id)
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [_factor_catalog_row_to_dict(row) for row in rows]
    except Exception as exc:
        logger.exception("Failed to list factor catalogs")
        raise DataAccessError("Failed to list factor catalogs.") from exc


def persist_factor_materializations(
    rows_payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not rows_payload:
        return []
    try:
        with SessionLocal() as session:
            rows: list[FactorMaterialization] = []
            for payload in rows_payload:
                row = FactorMaterialization(
                    run_id=payload.get("run_id"),
                    catalog_id=payload.get("catalog_id"),
                    factor_id=payload["factor_id"],
                    symbol=payload["symbol"],
                    market=payload["market"],
                    trading_date=payload["trading_date"],
                    value=payload.get("value"),
                    source_available_at=payload.get("source_available_at"),
                    factor_available_ts=payload.get("factor_available_ts"),
                    availability_mode=payload["availability_mode"],
                )
                session.add(row)
                rows.append(row)
            session.commit()
            return [_factor_materialization_row_to_dict(row) for row in rows]
    except Exception as exc:
        logger.exception("Failed to persist factor materializations")
        raise DataAccessError("Failed to persist factor materializations.") from exc


def list_factor_materializations(
    *, run_id: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(FactorMaterialization)
            if run_id is not None:
                stmt = stmt.where(FactorMaterialization.run_id == run_id)
            stmt = stmt.order_by(
                desc(FactorMaterialization.trading_date),
                desc(FactorMaterialization.id),
            ).limit(limit)
            return [
                _factor_materialization_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list factor materializations")
        raise DataAccessError("Failed to list factor materializations.") from exc


def persist_factor_usability_observations(rows_payload: list[dict[str, Any]]) -> None:
    if not rows_payload:
        return
    try:
        with SessionLocal() as session:
            for payload in rows_payload:
                session.add(
                    FactorUsabilityObservation(
                        run_id=payload.get("run_id"),
                        catalog_id=payload.get("catalog_id"),
                        trading_date=payload["trading_date"],
                        factor_id=payload["factor_id"],
                        coverage_ratio=payload["coverage_ratio"],
                        materialization_latency_hours=payload.get(
                            "materialization_latency_hours"
                        ),
                        status=payload["status"],
                    )
                )
            session.commit()
    except Exception as exc:
        logger.exception("Failed to persist factor usability observations")
        raise DataAccessError(
            "Failed to persist factor usability observations."
        ) from exc


def list_factor_usability_observations(
    *, run_id: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(FactorUsabilityObservation)
            if run_id is not None:
                stmt = stmt.where(FactorUsabilityObservation.run_id == run_id)
            stmt = stmt.order_by(
                desc(FactorUsabilityObservation.trading_date),
                desc(FactorUsabilityObservation.id),
            ).limit(limit)
            return [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "catalog_id": row.catalog_id,
                    "trading_date": row.trading_date,
                    "factor_id": row.factor_id,
                    "coverage_ratio": row.coverage_ratio,
                    "materialization_latency_hours": row.materialization_latency_hours,
                    "status": row.status,
                    "created_at": normalize_created_at(row.created_at),
                }
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list factor usability observations")
        raise DataAccessError("Failed to list factor usability observations.") from exc


def persist_cluster_snapshot(
    snapshot_payload: dict[str, Any], memberships: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = ClusterSnapshot(**snapshot_payload)
            session.add(row)
            session.flush()
            membership_rows: list[dict[str, Any]] = []
            for payload in memberships:
                member = ClusterMembership(
                    snapshot_id=row.id,
                    symbol=payload["symbol"],
                    cluster_label=payload["cluster_label"],
                    distance_to_centroid=payload.get("distance_to_centroid"),
                )
                session.add(member)
                membership_rows.append(payload)
            session.commit()
            session.refresh(row)
            hydrated_memberships = [
                _cluster_membership_row_to_dict(member)
                for member in session.execute(
                    select(ClusterMembership)
                    .where(ClusterMembership.snapshot_id == row.id)
                    .order_by(ClusterMembership.symbol.asc())
                )
                .scalars()
                .all()
            ]
            return _cluster_snapshot_row_to_dict(row, hydrated_memberships)
    except Exception as exc:
        logger.exception("Failed to persist cluster snapshot")
        raise DataAccessError("Failed to persist cluster snapshot.") from exc


def get_cluster_snapshot(snapshot_id: int) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(ClusterSnapshot, snapshot_id)
            if row is None:
                raise DataNotFoundError(
                    f"Cluster snapshot '{snapshot_id}' was not found."
                )
            memberships = [
                _cluster_membership_row_to_dict(member)
                for member in session.execute(
                    select(ClusterMembership)
                    .where(ClusterMembership.snapshot_id == snapshot_id)
                    .order_by(ClusterMembership.symbol.asc())
                )
                .scalars()
                .all()
            ]
            return _cluster_snapshot_row_to_dict(row, memberships)
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load cluster snapshot snapshot_id=%s", snapshot_id)
        raise DataAccessError("Failed to load cluster snapshot.") from exc


def list_cluster_snapshots(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ClusterSnapshot)
                .order_by(desc(ClusterSnapshot.trading_date), desc(ClusterSnapshot.id))
                .limit(limit)
            )
            return [
                _cluster_snapshot_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list cluster snapshots")
        raise DataAccessError("Failed to list cluster snapshots.") from exc


def persist_peer_feature_run(
    run_payload: dict[str, Any], overlays: list[dict[str, Any]]
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = PeerFeatureRun(
                run_id=run_payload.get("run_id"),
                snapshot_id=run_payload.get("snapshot_id"),
                peer_policy_version=run_payload["peer_policy_version"],
                market=run_payload["market"],
                trading_date=run_payload["trading_date"],
                status=run_payload["status"],
                produced_feature_count=run_payload["produced_feature_count"],
                warning_count=run_payload["warning_count"],
                warning_json=json_dumps(run_payload.get("warnings", [])) or "[]",
            )
            session.add(row)
            session.flush()
            for payload in overlays:
                session.add(
                    PeerComparisonOverlay(
                        peer_feature_run_id=row.id,
                        symbol=payload["symbol"],
                        peer_symbol_count=payload["peer_symbol_count"],
                        peer_feature_value=payload.get("peer_feature_value"),
                        detail_json=json_dumps(payload.get("detail", {})) or "{}",
                    )
                )
            session.commit()
            session.refresh(row)
            overlay_rows = [
                _peer_overlay_row_to_dict(item)
                for item in session.execute(
                    select(PeerComparisonOverlay)
                    .where(PeerComparisonOverlay.peer_feature_run_id == row.id)
                    .order_by(PeerComparisonOverlay.symbol.asc())
                )
                .scalars()
                .all()
            ]
            return _peer_feature_run_row_to_dict(row, overlay_rows)
    except Exception as exc:
        logger.exception("Failed to persist peer feature run")
        raise DataAccessError("Failed to persist peer feature run.") from exc


def list_peer_feature_runs(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(PeerFeatureRun)
                .order_by(desc(PeerFeatureRun.trading_date), desc(PeerFeatureRun.id))
                .limit(limit)
            )
            return [
                _peer_feature_run_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list peer feature runs")
        raise DataAccessError("Failed to list peer feature runs.") from exc


def ensure_default_failure_taxonomies() -> None:
    defaults = [
        (
            "sim_profile_missing",
            "simulation_internal_v1",
            "configuration",
            "simulation profile is missing",
        ),
        (
            "kill_switch_active",
            "live_stub_v1",
            "control",
            "kill switch blocked the order",
        ),
        (
            "manual_confirmation_missing",
            "live_stub_v1",
            "control",
            "manual confirmation is required",
        ),
        ("risk_check_failed", "live_stub_v1", "risk", "risk checks rejected the order"),
    ]
    try:
        with SessionLocal() as session:
            existing_codes = set(
                session.execute(select(ExecutionFailureTaxonomy.code)).scalars().all()
            )
            for code, route, category, description in defaults:
                if code in existing_codes:
                    continue
                session.add(
                    ExecutionFailureTaxonomy(
                        code=code,
                        route=route,
                        category=category,
                        description=description,
                    )
                )
            try:
                session.commit()
            except IntegrityError:
                # A concurrent request may have inserted the same defaults between
                # our read and commit. Treat that case as success once all codes exist.
                session.rollback()
                refreshed_codes = set(
                    session.execute(select(ExecutionFailureTaxonomy.code))
                    .scalars()
                    .all()
                )
                required_codes = {code for code, _, _, _ in defaults}
                if not required_codes.issubset(refreshed_codes):
                    raise
    except Exception as exc:
        logger.exception("Failed to seed execution failure taxonomies")
        raise DataAccessError("Failed to seed execution failure taxonomies.") from exc


def ensure_simulation_profile(
    profile_id: str = "simulation_internal_default_v1",
    market: str = "TW",
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(SimulationProfile, profile_id) or SimulationProfile(
                id=profile_id
            )
            row.market = market
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "market": row.market,
                "ack_latency_seconds": row.ack_latency_seconds,
                "fill_latency_seconds": row.fill_latency_seconds,
                "slippage_bps": row.slippage_bps,
                "notes": row.notes,
                "created_at": normalize_created_at(row.created_at),
            }
    except Exception as exc:
        logger.exception(
            "Failed to ensure simulation profile profile_id=%s", profile_id
        )
        raise DataAccessError("Failed to ensure simulation profile.") from exc


def ensure_live_control_profile(
    profile_id: str = "live_stub_default_v1",
    market: str = "TW",
    live_control_version: str = "live_stub_controls_v1",
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(LiveControlProfile, profile_id) or LiveControlProfile(
                id=profile_id
            )
            row.market = market
            row.live_control_version = live_control_version
            row.detail_json = json_dumps({"route": "live_stub_v1"}) or "{}"
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "market": row.market,
                "live_control_version": row.live_control_version,
                "detail": json_loads(row.detail_json, {}),
                "created_at": normalize_created_at(row.created_at),
            }
    except Exception as exc:
        logger.exception(
            "Failed to ensure live control profile profile_id=%s", profile_id
        )
        raise DataAccessError("Failed to ensure live control profile.") from exc


def persist_execution_order(
    order_payload: dict[str, Any],
    *,
    events: list[dict[str, Any]],
    fills: list[dict[str, Any]] | None = None,
    positions: list[dict[str, Any]] | None = None,
    risk_checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = ExecutionOrder(**order_payload)
            session.add(row)
            session.flush()
            for payload in events:
                session.add(
                    ExecutionOrderEvent(
                        order_id=row.id,
                        event_type=payload["event_type"],
                        event_ts=payload["event_ts"],
                        detail_json=json_dumps(payload.get("detail", {})) or "{}",
                    )
                )
            for payload in fills or []:
                session.add(
                    ExecutionFillEvent(
                        order_id=row.id,
                        fill_ts=payload["fill_ts"],
                        fill_price=payload["fill_price"],
                        quantity=payload["quantity"],
                        slippage_bps=payload.get("slippage_bps"),
                    )
                )
            for payload in positions or []:
                session.add(
                    ExecutionPositionSnapshot(
                        order_id=row.id,
                        run_id=payload.get("run_id"),
                        route=payload["route"],
                        market=payload["market"],
                        symbol=payload["symbol"],
                        quantity=payload["quantity"],
                        avg_price=payload["avg_price"],
                        snapshot_ts=payload["snapshot_ts"],
                    )
                )
            for payload in risk_checks or []:
                session.add(
                    LiveRiskCheck(
                        order_id=row.id,
                        status=payload["status"],
                        detail_json=json_dumps(payload.get("detail", {})) or "{}",
                        checked_at=payload["checked_at"],
                    )
                )
            session.commit()
            session.refresh(row)
            return get_execution_order(row.id)
    except Exception as exc:
        logger.exception("Failed to persist execution order")
        raise DataAccessError("Failed to persist execution order.") from exc


def get_execution_order(order_id: int) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(ExecutionOrder, order_id)
            if row is None:
                raise DataNotFoundError(f"Execution order '{order_id}' was not found.")
            events = [
                _execution_event_row_to_dict(event)
                for event in session.execute(
                    select(ExecutionOrderEvent)
                    .where(ExecutionOrderEvent.order_id == order_id)
                    .order_by(
                        ExecutionOrderEvent.event_ts.asc(), ExecutionOrderEvent.id.asc()
                    )
                )
                .scalars()
                .all()
            ]
            fills = [
                _execution_fill_row_to_dict(fill)
                for fill in session.execute(
                    select(ExecutionFillEvent)
                    .where(ExecutionFillEvent.order_id == order_id)
                    .order_by(
                        ExecutionFillEvent.fill_ts.asc(), ExecutionFillEvent.id.asc()
                    )
                )
                .scalars()
                .all()
            ]
            positions = [
                _execution_position_row_to_dict(position)
                for position in session.execute(
                    select(ExecutionPositionSnapshot)
                    .where(ExecutionPositionSnapshot.order_id == order_id)
                    .order_by(ExecutionPositionSnapshot.snapshot_ts.asc())
                )
                .scalars()
                .all()
            ]
            risk_checks = [
                _risk_check_row_to_dict(check)
                for check in session.execute(
                    select(LiveRiskCheck)
                    .where(LiveRiskCheck.order_id == order_id)
                    .order_by(LiveRiskCheck.checked_at.asc())
                )
                .scalars()
                .all()
            ]
            return _execution_order_row_to_dict(
                row,
                events=events,
                fills=fills,
                positions=positions,
                risk_checks=risk_checks,
            )
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load execution order order_id=%s", order_id)
        raise DataAccessError("Failed to load execution order.") from exc


def list_execution_orders(
    *, route: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(ExecutionOrder)
            if route is not None:
                stmt = stmt.where(ExecutionOrder.route == route)
            stmt = stmt.order_by(
                desc(ExecutionOrder.created_at), desc(ExecutionOrder.id)
            ).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [get_execution_order(row.id) for row in rows]
    except Exception as exc:
        logger.exception("Failed to list execution orders")
        raise DataAccessError("Failed to list execution orders.") from exc


def persist_kill_switch_event(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = KillSwitchEvent(**payload)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _kill_switch_row_to_dict(row)
    except Exception as exc:
        logger.exception("Failed to persist kill switch event")
        raise DataAccessError("Failed to persist kill switch event.") from exc


def list_kill_switch_events(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(KillSwitchEvent)
                .order_by(desc(KillSwitchEvent.created_at), desc(KillSwitchEvent.id))
                .limit(limit)
            )
            return [
                _kill_switch_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list kill switch events")
        raise DataAccessError("Failed to list kill switch events.") from exc


def get_effective_kill_switch(market: str | None = None) -> dict[str, Any] | None:
    try:
        with SessionLocal() as session:
            stmt = select(KillSwitchEvent)
            if market is not None:
                stmt = stmt.where(
                    (KillSwitchEvent.scope_type == "global")
                    | (
                        (KillSwitchEvent.scope_type == "market")
                        & (KillSwitchEvent.market == market)
                    )
                )
            stmt = stmt.order_by(
                desc(KillSwitchEvent.created_at), desc(KillSwitchEvent.id)
            ).limit(1)
            row = session.execute(stmt).scalars().first()
            return _kill_switch_row_to_dict(row) if row is not None else None
    except Exception as exc:
        logger.exception("Failed to load effective kill switch")
        raise DataAccessError("Failed to load effective kill switch.") from exc


def persist_adaptive_profile(
    profile_payload: dict[str, Any], rollout_payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(
                AdaptiveProfile, profile_payload["id"]
            ) or AdaptiveProfile(id=profile_payload["id"])
            row.market = profile_payload["market"]
            row.reward_definition_version = profile_payload["reward_definition_version"]
            row.state_definition_version = profile_payload["state_definition_version"]
            row.notes = profile_payload.get("notes")
            session.add(row)
            rollout = session.get(
                AdaptiveRolloutControl, rollout_payload["id"]
            ) or AdaptiveRolloutControl(id=rollout_payload["id"])
            rollout.profile_id = row.id
            rollout.rollout_control_version = rollout_payload["rollout_control_version"]
            rollout.mode = rollout_payload["mode"]
            rollout.detail_json = json_dumps(rollout_payload.get("detail", {})) or "{}"
            session.add(rollout)
            session.commit()
            session.refresh(row)
            session.refresh(rollout)
            return _adaptive_profile_row_to_dict(row, rollout)
    except Exception as exc:
        logger.exception(
            "Failed to persist adaptive profile profile_id=%s", profile_payload["id"]
        )
        raise DataAccessError("Failed to persist adaptive profile.") from exc


def get_adaptive_profile(profile_id: str) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(AdaptiveProfile, profile_id)
            if row is None:
                raise DataNotFoundError(
                    f"Adaptive profile '{profile_id}' was not found."
                )
            rollout = (
                session.execute(
                    select(AdaptiveRolloutControl)
                    .where(AdaptiveRolloutControl.profile_id == row.id)
                    .order_by(
                        desc(AdaptiveRolloutControl.created_at),
                        AdaptiveRolloutControl.id,
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return _adaptive_profile_row_to_dict(row, rollout)
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load adaptive profile profile_id=%s", profile_id)
        raise DataAccessError("Failed to load adaptive profile.") from exc


def list_adaptive_profiles(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(AdaptiveProfile)
                .order_by(desc(AdaptiveProfile.created_at), AdaptiveProfile.id)
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [get_adaptive_profile(row.id) for row in rows]
    except Exception as exc:
        logger.exception("Failed to list adaptive profiles")
        raise DataAccessError("Failed to list adaptive profiles.") from exc


def persist_adaptive_training_run(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = AdaptiveTrainingRun(
                profile_id=payload.get("profile_id"),
                run_id=payload.get("run_id"),
                market=payload["market"],
                adaptive_mode=payload["adaptive_mode"],
                reward_definition_version=payload["reward_definition_version"],
                state_definition_version=payload["state_definition_version"],
                rollout_control_version=payload["rollout_control_version"],
                status=payload["status"],
                dataset_summary_json=json_dumps(payload.get("dataset_summary", {}))
                or "{}",
                artifact_registry_json=json_dumps(payload.get("artifact_registry", {}))
                or "{}",
                validation_error=payload.get("validation_error"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _adaptive_training_run_row_to_dict(row)
    except Exception as exc:
        logger.exception("Failed to persist adaptive training run")
        raise DataAccessError("Failed to persist adaptive training run.") from exc


def list_adaptive_training_runs(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(AdaptiveTrainingRun)
                .order_by(
                    desc(AdaptiveTrainingRun.created_at), desc(AdaptiveTrainingRun.id)
                )
                .limit(limit)
            )
            return [
                _adaptive_training_run_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list adaptive training runs")
        raise DataAccessError("Failed to list adaptive training runs.") from exc


def persist_adaptive_surface_exclusion(payload: dict[str, Any]) -> None:
    try:
        with SessionLocal() as session:
            row = (
                session.execute(
                    select(AdaptiveSurfaceExclusion).where(
                        AdaptiveSurfaceExclusion.run_id == payload["run_id"]
                    )
                )
                .scalars()
                .first()
            )
            row = row or AdaptiveSurfaceExclusion(run_id=payload["run_id"])
            row.exclusion_surface = payload["exclusion_surface"]
            row.reason = payload["reason"]
            session.add(row)
            session.commit()
    except Exception as exc:
        logger.exception(
            "Failed to persist adaptive surface exclusion run_id=%s",
            payload["run_id"],
        )
        raise DataAccessError("Failed to persist adaptive surface exclusion.") from exc


def list_adaptive_surface_exclusions(limit: int = 100) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(AdaptiveSurfaceExclusion)
                .order_by(
                    desc(AdaptiveSurfaceExclusion.created_at),
                    desc(AdaptiveSurfaceExclusion.id),
                )
                .limit(limit)
            )
            return [
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "exclusion_surface": row.exclusion_surface,
                    "reason": row.reason,
                    "created_at": normalize_created_at(row.created_at),
                }
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list adaptive surface exclusions")
        raise DataAccessError("Failed to list adaptive surface exclusions.") from exc
