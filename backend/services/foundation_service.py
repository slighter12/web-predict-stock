from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import desc, select

from ..database import (
    DailyOHLCV,
    ImportantEvent,
    SessionLocal,
    SymbolLifecycleRecord,
    TwCompanyProfile,
)
from ..errors import DataNotFoundError, UnsupportedConfigurationError
from ..repositories.foundation_repository import (
    ensure_default_failure_taxonomies,
    ensure_live_control_profile,
    ensure_simulation_profile,
    get_adaptive_profile,
    get_cluster_snapshot,
    get_effective_kill_switch,
    get_factor_catalog,
    list_adaptive_profiles,
    list_adaptive_surface_exclusions,
    list_adaptive_training_runs,
    list_cluster_snapshots,
    list_execution_orders,
    list_external_signal_audits,
    list_external_signal_records,
    list_external_signal_records_for_window,
    list_factor_catalogs,
    list_factor_materializations,
    list_factor_usability_observations,
    list_kill_switch_events,
    list_peer_feature_runs,
    persist_adaptive_profile,
    persist_adaptive_surface_exclusion,
    persist_adaptive_training_run,
    persist_cluster_snapshot,
    persist_execution_order,
    persist_external_signal_audit,
    persist_external_signal_ingestion,
    persist_factor_catalog,
    persist_factor_materializations,
    persist_factor_usability_observations,
    persist_kill_switch_event,
    persist_peer_feature_run,
)
from ..repositories.research_run_repository import get_research_run_record
from ..schemas.foundations import (
    AdaptiveProfileRequest,
    AdaptiveTrainingRunRequest,
    ClusterSnapshotRequest,
    ExternalSignalAuditRequest,
    ExternalSignalIngestionRequest,
    FactorCatalogRequest,
    LiveOrderRequest,
    PeerFeatureRunRequest,
    SimulationOrderRequest,
)
from ..schemas.research_runs import ResearchRunCreateRequest
from ..time_utils import utc_now

EXTERNAL_SOURCE_FAMILY = "tw_company_event_layer_v1"
EXTERNAL_LINEAGE_VERSION = "tw_company_event_lineage_v1"
SIMULATION_ADAPTER_VERSION = "simulation_internal_adapter_v1"
LIVE_CONTROL_VERSION = "live_stub_controls_v1"
ADAPTIVE_CONTRACT_VERSION = "adaptive_isolation_contract_v1"
PEER_COMPARISON_POLICY_VERSION = "peer_relative_overlay_v1"
PEER_POLICY_VERSION = "cluster_nearest_neighbors_v1"
DEFAULT_CLUSTER_SNAPSHOT_VERSION = "peer_cluster_kmeans_v1"
AUDIT_DRAW_RULE_VERSION = "deterministic_external_signal_audit_v1"
SUPPORTED_FACTOR_DEFINITIONS: dict[str, dict[str, str]] = {
    "company_listing_age_days_v1": {
        "display_name": "Company Listing Age Days",
        "formula_definition": "trading_date - listing_date",
        "lineage": EXTERNAL_LINEAGE_VERSION,
        "timing_semantics": "fallback_listing_date_pti",
        "missing_value_policy": "null_when_listing_date_unknown",
    },
    "important_event_count_30d_v1": {
        "display_name": "Important Event Count 30d",
        "formula_definition": "count(important_events publication_ts in trailing 30d)",
        "lineage": EXTERNAL_LINEAGE_VERSION,
        "timing_semantics": "official_publication_ts_pti",
        "missing_value_policy": "zero_when_no_events",
    },
    "lifecycle_transition_count_365d_v1": {
        "display_name": "Lifecycle Transition Count 365d",
        "formula_definition": "count(lifecycle effective_date in trailing 365d)",
        "lineage": EXTERNAL_LINEAGE_VERSION,
        "timing_semantics": "effective_date_fallback_pti",
        "missing_value_policy": "zero_when_no_transitions",
    },
}
_TW_MARKET_TIMEZONE = ZoneInfo("Asia/Taipei")


def _validate_execution_run_reference(run_id: str | None) -> None:
    if run_id is None:
        return
    get_research_run_record(run_id)


def _market_close_ts(trading_date: date) -> datetime:
    return datetime.combine(
        trading_date, time(13, 30), tzinfo=_TW_MARKET_TIMEZONE
    ).astimezone(timezone.utc)


def _fallback_market_ts(trading_date: date) -> datetime:
    return datetime.combine(
        trading_date, time(9, 0), tzinfo=_TW_MARKET_TIMEZONE
    ).astimezone(timezone.utc)


def _matching_cluster_snapshots(
    *, market: str, snapshot_version: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in list_cluster_snapshots(limit=200)
        if item["snapshot_version"] == snapshot_version and item["market"] == market
    ]


def _load_source_rows(
    *, coverage_start: date, coverage_end: date, market: str
) -> tuple[list[TwCompanyProfile], list[SymbolLifecycleRecord], list[ImportantEvent]]:
    with SessionLocal() as session:
        profiles = (
            session.execute(
                select(TwCompanyProfile)
                .where(TwCompanyProfile.market == market)
                .where(TwCompanyProfile.created_at.is_not(None))
                .order_by(TwCompanyProfile.symbol.asc())
            )
            .scalars()
            .all()
        )
        lifecycle = (
            session.execute(
                select(SymbolLifecycleRecord)
                .where(SymbolLifecycleRecord.market == market)
                .where(SymbolLifecycleRecord.effective_date >= coverage_start)
                .where(SymbolLifecycleRecord.effective_date <= coverage_end)
                .order_by(
                    SymbolLifecycleRecord.effective_date.asc(),
                    SymbolLifecycleRecord.id.asc(),
                )
            )
            .scalars()
            .all()
        )
        events = (
            session.execute(
                select(ImportantEvent)
                .where(ImportantEvent.market == market)
                .where(ImportantEvent.effective_date.is_not(None))
                .where(ImportantEvent.effective_date >= coverage_start)
                .where(ImportantEvent.effective_date <= coverage_end)
                .order_by(
                    ImportantEvent.event_publication_ts.asc(), ImportantEvent.id.asc()
                )
            )
            .scalars()
            .all()
        )
    return list(profiles), list(lifecycle), list(events)


def create_external_signal_ingestion(
    request: ExternalSignalIngestionRequest,
) -> dict[str, Any]:
    profiles, lifecycle_rows, events = _load_source_rows(
        coverage_start=request.coverage_start,
        coverage_end=request.coverage_end,
        market=request.market,
    )
    signal_rows: list[dict[str, Any]] = []
    for profile in profiles:
        if profile.listing_date is None:
            continue
        if not (request.coverage_start <= profile.listing_date <= request.coverage_end):
            continue
        signal_rows.append(
            {
                "source_family": request.source_family,
                "source_record_type": "company_profile",
                "symbol": profile.symbol,
                "market": request.market,
                "effective_date": profile.listing_date,
                "available_at": _fallback_market_ts(profile.listing_date),
                "availability_mode": "fallback",
                "lineage_version": EXTERNAL_LINEAGE_VERSION,
                "detail": {
                    "exchange": profile.exchange,
                    "board": profile.board,
                    "industry_category": profile.industry_category,
                },
            }
        )
    for row in lifecycle_rows:
        signal_rows.append(
            {
                "source_family": request.source_family,
                "source_record_type": "lifecycle_record",
                "symbol": row.symbol,
                "market": request.market,
                "effective_date": row.effective_date,
                "available_at": _fallback_market_ts(row.effective_date),
                "availability_mode": "fallback",
                "lineage_version": EXTERNAL_LINEAGE_VERSION,
                "detail": {
                    "event_type": row.event_type,
                    "reference_symbol": row.reference_symbol,
                    "source_name": row.source_name,
                },
            }
        )
    for row in events:
        signal_rows.append(
            {
                "source_family": request.source_family,
                "source_record_type": "important_event",
                "symbol": row.symbol,
                "market": request.market,
                "effective_date": row.effective_date,
                "available_at": row.event_publication_ts,
                "availability_mode": (
                    "exact" if row.event_publication_ts is not None else "unresolved"
                ),
                "lineage_version": EXTERNAL_LINEAGE_VERSION,
                "detail": {
                    "event_type": row.event_type,
                    "timestamp_source_class": row.timestamp_source_class,
                    "source_name": row.source_name,
                },
            }
        )
    archive_payload = {
        "source_family": request.source_family,
        "market": request.market,
        "coverage_start": request.coverage_start,
        "coverage_end": request.coverage_end,
        "record_count": len(signal_rows),
        "payload_body": str(
            {
                "profile_count": len(profiles),
                "lifecycle_count": len(lifecycle_rows),
                "important_event_count": len(events),
            }
        ),
        "notes": request.notes,
    }
    return persist_external_signal_ingestion(archive_payload, signal_rows)


def create_external_signal_audit(request: ExternalSignalAuditRequest) -> dict[str, Any]:
    records = list_external_signal_records_for_window(
        source_family=request.source_family,
        market=request.market,
        window_start=request.audit_window_start,
        window_end=request.audit_window_end,
    )
    total = len(records)
    sample_target = min(total, max(50, math.ceil(total * 0.05))) if total else 0
    ordered_records = sorted(
        records, key=lambda item: (item["effective_date"], item["id"])
    )
    fallback_records = [
        item for item in ordered_records if item["availability_mode"] == "fallback"
    ]
    fallback_target = min(20, len(fallback_records))
    fallback_sample = fallback_records[: min(fallback_target, sample_target)]
    selected_ids = {item["id"] for item in fallback_sample}
    remaining_slots = max(sample_target - len(fallback_sample), 0)
    remainder = [item for item in ordered_records if item["id"] not in selected_ids][
        :remaining_slots
    ]
    sample = sorted(
        [*fallback_sample, *remainder],
        key=lambda item: (item["effective_date"], item["id"]),
    )
    undocumented_count = len(
        [item for item in sample if item["availability_mode"] == "unresolved"]
    )
    return persist_external_signal_audit(
        {
            "source_family": request.source_family,
            "market": request.market,
            "audit_window_start": request.audit_window_start,
            "audit_window_end": request.audit_window_end,
            "sample_size": len(sample),
            "fallback_sample_size": len(fallback_sample),
            "undocumented_count": undocumented_count,
            "draw_rule_version": AUDIT_DRAW_RULE_VERSION,
            "result": {
                "source_window_record_count": total,
                "sample_target": sample_target,
                "fallback_target": fallback_target,
                "ordering_key": ["effective_date", "id"],
                "exact_count": len(
                    [item for item in sample if item["availability_mode"] == "exact"]
                ),
                "fallback_count": len(
                    [item for item in sample if item["availability_mode"] == "fallback"]
                ),
                "sample_record_ids": [item["id"] for item in sample],
                "fallback_record_ids": [item["id"] for item in fallback_sample],
                "undocumented_ids": [
                    item["id"]
                    for item in sample
                    if item["availability_mode"] == "unresolved"
                ],
            },
        }
    )


def list_external_signal_ingestions(limit: int = 50) -> list[dict[str, Any]]:
    # The archive list is currently represented through signal ingestions only.
    return list_external_signal_records(limit=limit)


def list_external_signals(limit: int = 200) -> list[dict[str, Any]]:
    return list_external_signal_records(limit=limit)


def list_external_signal_audit_runs(limit: int = 50) -> list[dict[str, Any]]:
    return list_external_signal_audits(limit=limit)


def create_factor_catalog(request: FactorCatalogRequest) -> dict[str, Any]:
    for entry in request.entries:
        if (
            entry.scoring_eligible
            and entry.factor_id not in SUPPORTED_FACTOR_DEFINITIONS
        ):
            raise UnsupportedConfigurationError(
                f"Unsupported scoring factor '{entry.factor_id}'."
            )
        if entry.scoring_eligible and (
            not entry.lineage
            or not entry.timing_semantics
            or not entry.missing_value_policy
        ):
            raise UnsupportedConfigurationError(
                "Scoring-eligible factor entries must declare lineage, timing semantics, and missing-value policy."
            )
    return persist_factor_catalog(request.model_dump(mode="json"))


def _load_symbol_external_context(symbol: str, market: str) -> dict[str, Any]:
    with SessionLocal() as session:
        profile = (
            session.execute(
                select(TwCompanyProfile)
                .where(TwCompanyProfile.symbol == symbol)
                .where(TwCompanyProfile.market == market)
                .order_by(desc(TwCompanyProfile.updated_at), desc(TwCompanyProfile.id))
                .limit(1)
            )
            .scalars()
            .first()
        )
        events = (
            session.execute(
                select(ImportantEvent)
                .where(ImportantEvent.symbol == symbol)
                .where(ImportantEvent.market == market)
                .order_by(
                    ImportantEvent.event_publication_ts.asc(), ImportantEvent.id.asc()
                )
            )
            .scalars()
            .all()
        )
        lifecycle = (
            session.execute(
                select(SymbolLifecycleRecord)
                .where(SymbolLifecycleRecord.symbol == symbol)
                .where(SymbolLifecycleRecord.market == market)
                .order_by(
                    SymbolLifecycleRecord.effective_date.asc(),
                    SymbolLifecycleRecord.id.asc(),
                )
            )
            .scalars()
            .all()
        )
    return {"profile": profile, "events": list(events), "lifecycle": list(lifecycle)}


def _factor_value_for_date(
    *, factor_id: str, trading_date: date, context: dict[str, Any]
) -> tuple[float | None, datetime | None, str]:
    profile = context["profile"]
    events = context["events"]
    lifecycle = context["lifecycle"]
    if factor_id == "company_listing_age_days_v1":
        if profile is None or profile.listing_date is None:
            return None, None, "unresolved"
        return (
            float((trading_date - profile.listing_date).days),
            _fallback_market_ts(profile.listing_date),
            "fallback",
        )
    if factor_id == "important_event_count_30d_v1":
        lower = trading_date - timedelta(days=30)
        relevant = [
            item
            for item in events
            if item.event_publication_ts is not None
            and lower <= item.event_publication_ts.date() <= trading_date
        ]
        latest_ts = max((item.event_publication_ts for item in relevant), default=None)
        return float(len(relevant)), latest_ts, "exact" if latest_ts else "fallback"
    if factor_id == "lifecycle_transition_count_365d_v1":
        lower = trading_date - timedelta(days=365)
        relevant = [
            item for item in lifecycle if lower <= item.effective_date <= trading_date
        ]
        latest_ts = (
            _fallback_market_ts(
                max((item.effective_date for item in relevant), default=trading_date)
            )
            if relevant
            else _fallback_market_ts(trading_date)
        )
        return float(len(relevant)), latest_ts, "fallback"
    raise UnsupportedConfigurationError(f"Unsupported factor '{factor_id}'.")


def materialize_run_factors(
    request: ResearchRunCreateRequest,
    *,
    run_id: str,
    symbol: str,
    df_features: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not request.factor_catalog_version:
        return df_features, []
    catalog = get_factor_catalog(request.factor_catalog_version)
    selected_factor_ids = request.scoring_factor_ids or [
        entry["factor_id"] for entry in catalog["entries"] if entry["scoring_eligible"]
    ]
    if not selected_factor_ids:
        return df_features, []
    catalog_entry_map = {entry["factor_id"]: entry for entry in catalog["entries"]}
    for factor_id in selected_factor_ids:
        if factor_id not in catalog_entry_map:
            raise UnsupportedConfigurationError(
                f"Factor '{factor_id}' is not declared in catalog '{catalog['id']}'."
            )
    context = _load_symbol_external_context(symbol, request.market)
    rows: list[dict[str, Any]] = []
    augmented = df_features.copy()
    for factor_id in selected_factor_ids:
        values: list[float | None] = []
        factor_rows: list[dict[str, Any]] = []
        for index_value in augmented.index:
            trading_date = pd.Timestamp(index_value).date()
            value, source_available_at, availability_mode = _factor_value_for_date(
                factor_id=factor_id,
                trading_date=trading_date,
                context=context,
            )
            values.append(value)
            factor_rows.append(
                {
                    "run_id": run_id,
                    "catalog_id": catalog["id"],
                    "factor_id": factor_id,
                    "symbol": symbol,
                    "market": request.market,
                    "trading_date": trading_date,
                    "value": value,
                    "source_available_at": source_available_at,
                    "factor_available_ts": _market_close_ts(trading_date),
                    "availability_mode": availability_mode,
                }
            )
        augmented[factor_id] = values
        rows.extend(factor_rows)
    return augmented, rows


def persist_run_factor_observations(
    *, run_id: str, catalog_id: str | None, materializations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    persisted = persist_factor_materializations(materializations)
    grouped: dict[tuple[date, str], list[dict[str, Any]]] = {}
    for item in persisted:
        grouped.setdefault((item["trading_date"], item["factor_id"]), []).append(item)
    observations: list[dict[str, Any]] = []
    for (trading_date, factor_id), rows in grouped.items():
        non_null = [row for row in rows if row["value"] is not None]
        latencies: list[float] = []
        for row in non_null:
            source_at = row.get("source_available_at")
            factor_at = row.get("factor_available_ts")
            if source_at and factor_at:
                latencies.append((factor_at - source_at).total_seconds() / 3600.0)
        observations.append(
            {
                "run_id": run_id,
                "catalog_id": catalog_id,
                "trading_date": trading_date,
                "factor_id": factor_id,
                "coverage_ratio": float(len(non_null) / max(len(rows), 1)),
                "materialization_latency_hours": max(latencies) if latencies else None,
                "status": "usable" if non_null else "insufficient_sample",
            }
        )
    persist_factor_usability_observations(observations)
    return persisted


def list_factor_catalog_records(limit: int = 50) -> list[dict[str, Any]]:
    return list_factor_catalogs(limit=limit)


def list_factor_materialization_records(
    *, run_id: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    return list_factor_materializations(run_id=run_id, limit=limit)


def list_factor_usability_records(
    *, run_id: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    return list_factor_usability_observations(run_id=run_id, limit=limit)


def _load_cluster_frame(
    *, market: str, trading_date: date
) -> tuple[list[str], pd.DataFrame]:
    with SessionLocal() as session:
        price_rows = (
            session.execute(
                select(DailyOHLCV)
                .where(DailyOHLCV.market == market)
                .where(DailyOHLCV.date == trading_date)
                .order_by(DailyOHLCV.symbol.asc())
            )
            .scalars()
            .all()
        )
        symbols = sorted({row.symbol for row in price_rows})
        if not symbols:
            raise DataNotFoundError(
                "At least two symbols with daily data are required."
            )
        lifecycle_rows = (
            session.execute(
                select(SymbolLifecycleRecord)
                .where(SymbolLifecycleRecord.market == market)
                .where(SymbolLifecycleRecord.symbol.in_(symbols))
                .where(SymbolLifecycleRecord.effective_date <= trading_date)
                .order_by(
                    SymbolLifecycleRecord.symbol.asc(),
                    SymbolLifecycleRecord.effective_date.asc(),
                    SymbolLifecycleRecord.id.asc(),
                )
            )
            .scalars()
            .all()
        )
        profiles = (
            session.execute(
                select(TwCompanyProfile)
                .where(TwCompanyProfile.market == market)
                .where(TwCompanyProfile.symbol.in_(symbols))
                .order_by(TwCompanyProfile.symbol.asc())
            )
            .scalars()
            .all()
        )
        event_rows = (
            session.execute(
                select(ImportantEvent)
                .where(ImportantEvent.market == market)
                .where(ImportantEvent.effective_date.is_not(None))
                .where(ImportantEvent.effective_date <= trading_date)
            )
            .scalars()
            .all()
        )
    lifecycle_by_symbol: dict[str, list[SymbolLifecycleRecord]] = {}
    for row in lifecycle_rows:
        lifecycle_by_symbol.setdefault(row.symbol, []).append(row)
    profile_by_symbol = {profile.symbol: profile for profile in profiles}
    active_symbols = {
        symbol
        for symbol in symbols
        if _is_symbol_active_on_date(
            symbol=symbol,
            trading_date=trading_date,
            profile=profile_by_symbol.get(symbol),
            lifecycle_rows=lifecycle_by_symbol.get(symbol, []),
        )
    }
    frame_rows: list[dict[str, Any]] = []
    for price in price_rows:
        if price.symbol not in active_symbols:
            continue
        event_count = len(
            [
                row
                for row in event_rows
                if row.symbol == price.symbol
                and row.event_publication_ts.date() >= trading_date - timedelta(days=30)
            ]
        )
        frame_rows.append(
            {
                "symbol": price.symbol,
                "close": price.close,
                "volume": float(price.volume),
                "important_event_count_30d": float(event_count),
            }
        )
    if len(frame_rows) < 2:
        raise DataNotFoundError("At least two symbols with daily data are required.")
    frame = pd.DataFrame(frame_rows).set_index("symbol")
    return list(frame.index), frame


def _is_symbol_active_on_date(
    *,
    symbol: str,
    trading_date: date,
    profile: TwCompanyProfile | None,
    lifecycle_rows: list[SymbolLifecycleRecord],
) -> bool:
    if profile and profile.listing_date and trading_date < profile.listing_date:
        return False
    relevant_rows = sorted(
        [row for row in lifecycle_rows if row.symbol == symbol],
        key=lambda row: (row.effective_date, row.id),
    )
    if not relevant_rows:
        return True
    is_active = False
    for row in relevant_rows:
        if row.event_type in {"listing", "re_listing"}:
            is_active = True
        elif row.event_type == "delisting":
            is_active = False
    return is_active


def create_cluster_snapshot(request: ClusterSnapshotRequest) -> dict[str, Any]:
    symbols, frame = _load_cluster_frame(
        market=request.market, trading_date=request.trading_date
    )
    cluster_count = max(1, min(request.cluster_count, len(symbols)))
    scaled = StandardScaler().fit_transform(frame)
    model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
    labels = model.fit_predict(scaled)
    distances = model.transform(scaled)
    memberships = []
    for idx, symbol in enumerate(symbols):
        label = int(labels[idx])
        memberships.append(
            {
                "symbol": symbol,
                "cluster_label": f"cluster_{label}",
                "distance_to_centroid": float(distances[idx][label]),
            }
        )
    return persist_cluster_snapshot(
        {
            "snapshot_version": request.snapshot_version,
            "run_id": None,
            "factor_catalog_version": request.factor_catalog_version,
            "market": request.market,
            "trading_date": request.trading_date,
            "cluster_count": cluster_count,
            "symbol_count": len(symbols),
            "status": "succeeded",
            "notes": request.notes,
        },
        memberships,
    )


def list_cluster_snapshot_records(limit: int = 50) -> list[dict[str, Any]]:
    return list_cluster_snapshots(limit=limit)


def create_peer_feature_run(request: PeerFeatureRunRequest) -> dict[str, Any]:
    snapshot = get_cluster_snapshot(request.snapshot_id)
    overlays, warnings = _build_peer_overlays(
        snapshot,
        symbol_limit=request.symbol_limit,
        warning_template="{symbol} has no peer in snapshot {snapshot_id}.",
    )
    return persist_peer_feature_run(
        {
            "run_id": None,
            "snapshot_id": snapshot["id"],
            "peer_policy_version": request.peer_policy_version,
            "market": snapshot["market"],
            "trading_date": snapshot["trading_date"],
            "status": "succeeded" if overlays else "failed",
            "produced_feature_count": len(
                [item for item in overlays if item["peer_symbol_count"] > 0]
            ),
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        overlays,
    )


def list_peer_feature_run_records(limit: int = 50) -> list[dict[str, Any]]:
    return list_peer_feature_runs(limit=limit)


def build_run_foundation_context(
    request: ResearchRunCreateRequest,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    context = {
        "factor_catalog_version": request.factor_catalog_version,
        "scoring_factor_ids": request.scoring_factor_ids,
        "external_signal_policy_version": request.external_signal_policy_version
        or EXTERNAL_SOURCE_FAMILY,
        "external_lineage_version": EXTERNAL_LINEAGE_VERSION
        if request.factor_catalog_version
        else None,
        "cluster_snapshot_version": request.cluster_snapshot_version,
        "peer_policy_version": request.peer_policy_version,
        "peer_comparison_policy_version": (
            PEER_COMPARISON_POLICY_VERSION if request.peer_policy_version else None
        ),
        "execution_route": request.execution_route,
        "simulation_profile_id": request.simulation_profile_id,
        "simulation_adapter_version": None,
        "live_control_profile_id": request.live_control_profile_id,
        "live_control_version": None,
        "adaptive_mode": request.adaptive_mode,
        "adaptive_profile_id": request.adaptive_profile_id,
        "adaptive_contract_version": None,
        "reward_definition_version": request.reward_definition_version,
        "state_definition_version": request.state_definition_version,
        "rollout_control_version": request.rollout_control_version,
    }
    if request.factor_catalog_version:
        catalog = get_factor_catalog(request.factor_catalog_version)
        if request.scoring_factor_ids:
            missing = sorted(
                set(request.scoring_factor_ids)
                - {entry["factor_id"] for entry in catalog["entries"]}
            )
            if missing:
                raise UnsupportedConfigurationError(
                    f"Unknown factor IDs for catalog '{catalog['id']}': {', '.join(missing)}."
                )
    if request.cluster_snapshot_version:
        snapshots = _matching_cluster_snapshots(
            market=request.market,
            snapshot_version=request.cluster_snapshot_version,
        )
        if not snapshots:
            warnings.append(
                f"No cluster snapshot found for market '{request.market}' and version '{request.cluster_snapshot_version}'. Peer features will be skipped."
            )
    if request.execution_route == "simulation_internal_v1":
        profile = ensure_simulation_profile(
            request.simulation_profile_id or "simulation_internal_default_v1",
            market=request.market,
        )
        context["simulation_profile_id"] = profile["id"]
        context["simulation_adapter_version"] = SIMULATION_ADAPTER_VERSION
    if request.execution_route == "live_stub_v1":
        ensure_default_failure_taxonomies()
        profile = ensure_live_control_profile(
            request.live_control_profile_id or "live_stub_default_v1",
            market=request.market,
            live_control_version=LIVE_CONTROL_VERSION,
        )
        context["live_control_profile_id"] = profile["id"]
        context["live_control_version"] = LIVE_CONTROL_VERSION
    if request.adaptive_mode != "off":
        get_adaptive_profile(request.adaptive_profile_id)
        context["adaptive_contract_version"] = ADAPTIVE_CONTRACT_VERSION
    return context, warnings


def persist_run_peer_outputs(
    *,
    run_id: str,
    request: ResearchRunCreateRequest,
) -> dict[str, Any] | None:
    if not request.cluster_snapshot_version or not request.peer_policy_version:
        return None
    snapshots = _matching_cluster_snapshots(
        market=request.market,
        snapshot_version=request.cluster_snapshot_version,
    )
    if not snapshots:
        return None
    snapshot = get_cluster_snapshot(snapshots[0]["id"])
    overlays, warnings = _build_peer_overlays(
        snapshot,
        symbol_limit=5,
        warning_template=("{symbol} had no peers under snapshot '{snapshot_version}'."),
    )
    return persist_peer_feature_run(
        {
            "run_id": run_id,
            "snapshot_id": snapshot["id"],
            "peer_policy_version": request.peer_policy_version,
            "market": snapshot["market"],
            "trading_date": snapshot["trading_date"],
            "status": "succeeded" if overlays else "failed",
            "produced_feature_count": len(
                [item for item in overlays if item["peer_symbol_count"] > 0]
            ),
            "warning_count": len(warnings),
            "warnings": warnings,
        },
        overlays,
    )


def _build_peer_overlays(
    snapshot: dict[str, Any],
    *,
    symbol_limit: int,
    warning_template: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for membership in snapshot["memberships"]:
        groups.setdefault(membership["cluster_label"], []).append(membership)
    overlays: list[dict[str, Any]] = []
    warnings: list[str] = []
    for items in groups.values():
        items = sorted(items, key=lambda item: item["distance_to_centroid"] or 0.0)
        for membership in items:
            peers = [item for item in items if item["symbol"] != membership["symbol"]][
                :symbol_limit
            ]
            if not peers:
                warnings.append(
                    warning_template.format(
                        symbol=membership["symbol"],
                        snapshot_id=snapshot["id"],
                        snapshot_version=snapshot["snapshot_version"],
                    )
                )
            overlays.append(
                {
                    "symbol": membership["symbol"],
                    "peer_symbol_count": len(peers),
                    "peer_feature_value": float(len(peers)),
                    "detail": {"peer_symbols": [peer["symbol"] for peer in peers]},
                }
            )
    return overlays, warnings


def build_run_peer_feature_map(
    request: ResearchRunCreateRequest,
) -> dict[str, dict[pd.Timestamp, dict[str, float]]]:
    if not request.cluster_snapshot_version or not request.peer_policy_version:
        return {}
    snapshots = _matching_cluster_snapshots(
        market=request.market,
        snapshot_version=request.cluster_snapshot_version,
    )
    if not snapshots:
        return {}
    feature_map: dict[str, dict[pd.Timestamp, dict[str, float]]] = {}
    ordered_snapshots = sorted(
        snapshots,
        key=lambda item: (item["trading_date"], item["id"]),
    )
    for snapshot_ref in ordered_snapshots:
        snapshot = get_cluster_snapshot(snapshot_ref["id"])
        overlays, _ = _build_peer_overlays(
            snapshot,
            symbol_limit=5,
            warning_template="{symbol}",
        )
        snapshot_ts = pd.Timestamp(snapshot["trading_date"])
        for overlay in overlays:
            feature_map.setdefault(overlay["symbol"], {})[snapshot_ts] = {
                "peer_symbol_count_p8": float(overlay["peer_symbol_count"]),
                "peer_feature_value_p8": float(overlay["peer_feature_value"] or 0.0),
            }
    return feature_map


def dispatch_run_execution_route(
    *,
    run_id: str,
    request: ResearchRunCreateRequest,
    signals: list[Any],
) -> list[dict[str, Any]]:
    if request.execution_route == "research_only":
        return []
    ensure_default_failure_taxonomies()
    latest_by_symbol: dict[str, Any] = {}
    for signal in signals:
        symbol = signal["symbol"] if isinstance(signal, dict) else signal.symbol
        latest_by_symbol[symbol] = signal
    if not latest_by_symbol:
        return []
    results: list[dict[str, Any]] = []
    if request.execution_route == "simulation_internal_v1":
        profile_id = request.simulation_profile_id or "simulation_internal_default_v1"
        ensure_simulation_profile(profile_id, market=request.market)
        for signal in latest_by_symbol.values():
            position = (
                signal["position"] if isinstance(signal, dict) else signal.position
            )
            symbol = signal["symbol"] if isinstance(signal, dict) else signal.symbol
            score = signal["score"] if isinstance(signal, dict) else signal.score
            quantity = max(position, 0.0) * 100.0
            submitted_at = utc_now()
            fill_price = float(max(score, 0.0) + 100.0)
            results.append(
                persist_execution_order(
                    {
                        "run_id": run_id,
                        "route": request.execution_route,
                        "market": request.market,
                        "symbol": symbol,
                        "side": "buy",
                        "quantity": quantity,
                        "requested_price": fill_price,
                        "status": "filled",
                        "simulation_profile_id": profile_id,
                        "live_control_profile_id": None,
                        "failure_code": None,
                        "manual_confirmation": True,
                        "rejection_reason": None,
                        "submitted_at": submitted_at,
                        "acknowledged_at": submitted_at + timedelta(seconds=5),
                    },
                    events=[
                        {
                            "event_type": "submitted",
                            "event_ts": submitted_at,
                            "detail": {"run_id": run_id},
                        },
                        {
                            "event_type": "acknowledged",
                            "event_ts": submitted_at + timedelta(seconds=5),
                            "detail": {"adapter_version": SIMULATION_ADAPTER_VERSION},
                        },
                        {
                            "event_type": "filled",
                            "event_ts": submitted_at + timedelta(seconds=30),
                            "detail": {"route": request.execution_route},
                        },
                        {
                            "event_type": "position_readback",
                            "event_ts": submitted_at + timedelta(seconds=35),
                            "detail": {"position_symbol": symbol},
                        },
                    ],
                    fills=[
                        {
                            "fill_ts": submitted_at + timedelta(seconds=30),
                            "fill_price": fill_price,
                            "quantity": quantity,
                            "slippage_bps": 5.0,
                        }
                    ],
                    positions=[
                        {
                            "run_id": run_id,
                            "route": request.execution_route,
                            "market": request.market,
                            "symbol": symbol,
                            "quantity": quantity,
                            "avg_price": fill_price,
                            "snapshot_ts": submitted_at + timedelta(seconds=35),
                        }
                    ],
                )
            )
        return results

    kill_switch = get_effective_kill_switch(request.market)
    kill_switch_active = bool(kill_switch and kill_switch["is_enabled"])
    live_control_profile = ensure_live_control_profile(
        request.live_control_profile_id or "live_stub_default_v1",
        market=request.market,
        live_control_version=LIVE_CONTROL_VERSION,
    )
    context_live_control_profile_id = live_control_profile["id"]
    for signal in latest_by_symbol.values():
        position = signal["position"] if isinstance(signal, dict) else signal.position
        symbol = signal["symbol"] if isinstance(signal, dict) else signal.symbol
        score = signal["score"] if isinstance(signal, dict) else signal.score
        submitted_at = utc_now()
        requested_price = float(max(score, 0.0) + 100.0)
        quantity = max(position, 0.0) * 100.0
        failure_code = None
        rejection_reason = None
        status = "accepted_for_stub_dispatch"
        manual_confirmation = request.manual_confirmed
        risk_checks = [
            {
                "status": "pass"
                if quantity > 0 and requested_price * quantity <= 1_000_000
                else "fail",
                "detail": {"notional": requested_price * quantity},
                "checked_at": submitted_at,
            }
        ]
        if kill_switch_active:
            failure_code = "kill_switch_active"
            rejection_reason = kill_switch["reason"] or "kill switch active"
            status = "rejected"
        elif not manual_confirmation:
            failure_code = "manual_confirmation_missing"
            rejection_reason = "manual confirmation is required"
            status = "rejected"
        elif risk_checks[0]["status"] != "pass":
            failure_code = "risk_check_failed"
            rejection_reason = "risk check failed"
            status = "rejected"
        execution_payload = _build_live_stub_execution_artifacts(
            run_id=run_id,
            market=request.market,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            requested_price=requested_price,
            live_control_profile_id=context_live_control_profile_id,
            manual_confirmation=manual_confirmation,
            status=status,
            failure_code=failure_code,
            rejection_reason=rejection_reason,
            submitted_at=submitted_at,
        )
        results.append(
            persist_execution_order(
                execution_payload["order"],
                events=execution_payload["events"],
                fills=execution_payload["fills"],
                positions=execution_payload["positions"],
                risk_checks=risk_checks,
            )
        )
    return results


def create_simulation_order(request: SimulationOrderRequest) -> dict[str, Any]:
    _validate_execution_run_reference(request.run_id)
    ensure_default_failure_taxonomies()
    profile = ensure_simulation_profile(
        request.simulation_profile_id or "simulation_internal_default_v1",
        market=request.market,
    )
    submitted_at = utc_now()
    requested_price = request.requested_price or 100.0
    return persist_execution_order(
        {
            "run_id": request.run_id,
            "route": "simulation_internal_v1",
            "market": request.market,
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "requested_price": requested_price,
            "status": "filled",
            "simulation_profile_id": profile["id"],
            "live_control_profile_id": None,
            "failure_code": None,
            "manual_confirmation": True,
            "rejection_reason": None,
            "submitted_at": submitted_at,
            "acknowledged_at": submitted_at
            + timedelta(seconds=profile["ack_latency_seconds"]),
        },
        events=[
            {"event_type": "submitted", "event_ts": submitted_at, "detail": {}},
            {
                "event_type": "acknowledged",
                "event_ts": submitted_at
                + timedelta(seconds=profile["ack_latency_seconds"]),
                "detail": {"adapter_version": SIMULATION_ADAPTER_VERSION},
            },
            {
                "event_type": "filled",
                "event_ts": submitted_at
                + timedelta(seconds=profile["fill_latency_seconds"]),
                "detail": {},
            },
            {
                "event_type": "position_readback",
                "event_ts": submitted_at
                + timedelta(seconds=profile["fill_latency_seconds"] + 5),
                "detail": {},
            },
        ],
        fills=[
            {
                "fill_ts": submitted_at
                + timedelta(seconds=profile["fill_latency_seconds"]),
                "fill_price": requested_price,
                "quantity": request.quantity,
                "slippage_bps": profile["slippage_bps"],
            }
        ],
        positions=[
            {
                "run_id": request.run_id,
                "route": "simulation_internal_v1",
                "market": request.market,
                "symbol": request.symbol,
                "quantity": request.quantity,
                "avg_price": requested_price,
                "snapshot_ts": submitted_at
                + timedelta(seconds=profile["fill_latency_seconds"] + 5),
            }
        ],
    )


def list_simulation_readbacks(limit: int = 100) -> list[dict[str, Any]]:
    return list_execution_orders(route="simulation_internal_v1", limit=limit)


def _build_live_stub_execution_artifacts(
    *,
    run_id: str | None,
    market: str,
    symbol: str,
    side: str,
    quantity: float,
    requested_price: float,
    live_control_profile_id: str | None,
    manual_confirmation: bool,
    status: str,
    failure_code: str | None,
    rejection_reason: str | None,
    submitted_at: datetime,
) -> dict[str, Any]:
    acknowledged_at = submitted_at + timedelta(seconds=5)
    filled_at = submitted_at + timedelta(seconds=30)
    readback_at = submitted_at + timedelta(seconds=35)
    order_payload = {
        "run_id": run_id,
        "route": "live_stub_v1",
        "market": market,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "requested_price": requested_price,
        "status": status,
        "simulation_profile_id": None,
        "live_control_profile_id": live_control_profile_id,
        "failure_code": failure_code,
        "manual_confirmation": manual_confirmation,
        "rejection_reason": rejection_reason,
        "submitted_at": submitted_at,
        "acknowledged_at": acknowledged_at
        if status == "accepted_for_stub_dispatch"
        else None,
    }
    if status == "rejected":
        return {
            "order": order_payload,
            "events": [
                {
                    "event_type": "rejected",
                    "event_ts": submitted_at,
                    "detail": {
                        "reason": rejection_reason,
                        "failure_code": failure_code,
                        "live_control_version": LIVE_CONTROL_VERSION,
                    },
                }
            ],
            "fills": [],
            "positions": [],
        }
    return {
        "order": order_payload,
        "events": [
            {
                "event_type": "submitted",
                "event_ts": submitted_at,
                "detail": {"live_control_version": LIVE_CONTROL_VERSION},
            },
            {
                "event_type": "acknowledged",
                "event_ts": acknowledged_at,
                "detail": {
                    "dispatch_status": status,
                    "live_control_version": LIVE_CONTROL_VERSION,
                },
            },
            {
                "event_type": "filled",
                "event_ts": filled_at,
                "detail": {
                    "route": "live_stub_v1",
                    "dispatch_status": status,
                    "stub_execution": True,
                },
            },
            {
                "event_type": "position_readback",
                "event_ts": readback_at,
                "detail": {
                    "position_symbol": symbol,
                    "dispatch_status": status,
                },
            },
        ],
        "fills": [
            {
                "fill_ts": filled_at,
                "fill_price": requested_price,
                "quantity": quantity,
                "slippage_bps": 0.0,
            }
        ],
        "positions": [
            {
                "run_id": run_id,
                "route": "live_stub_v1",
                "market": market,
                "symbol": symbol,
                "quantity": quantity,
                "avg_price": requested_price,
                "snapshot_ts": readback_at,
            }
        ],
    }


def create_live_order(request: LiveOrderRequest) -> dict[str, Any]:
    _validate_execution_run_reference(request.run_id)
    ensure_default_failure_taxonomies()
    live_control_profile = ensure_live_control_profile(
        request.live_control_profile_id or "live_stub_default_v1",
        market=request.market,
        live_control_version=LIVE_CONTROL_VERSION,
    )
    kill_switch = get_effective_kill_switch(request.market)
    submitted_at = utc_now()
    requested_price = request.requested_price or 100.0
    risk_status = (
        "pass"
        if request.quantity > 0 and requested_price * request.quantity <= 1_000_000
        else "fail"
    )
    failure_code = None
    rejection_reason = None
    status = "accepted_for_stub_dispatch"
    if kill_switch and kill_switch["is_enabled"]:
        failure_code = "kill_switch_active"
        rejection_reason = kill_switch.get("reason") or "kill switch active"
        status = "rejected"
    elif not request.manual_confirmed:
        failure_code = "manual_confirmation_missing"
        rejection_reason = "manual confirmation is required"
        status = "rejected"
    elif risk_status != "pass":
        failure_code = "risk_check_failed"
        rejection_reason = "risk check failed"
        status = "rejected"
    execution_payload = _build_live_stub_execution_artifacts(
        run_id=request.run_id,
        market=request.market,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        requested_price=requested_price,
        live_control_profile_id=live_control_profile["id"],
        manual_confirmation=request.manual_confirmed,
        status=status,
        failure_code=failure_code,
        rejection_reason=rejection_reason,
        submitted_at=submitted_at,
    )
    return persist_execution_order(
        execution_payload["order"],
        events=execution_payload["events"],
        fills=execution_payload["fills"],
        positions=execution_payload["positions"],
        risk_checks=[
            {
                "status": risk_status,
                "detail": {"notional": requested_price * request.quantity},
                "checked_at": submitted_at,
            }
        ],
    )


def create_kill_switch(request: Any) -> dict[str, Any]:
    return persist_kill_switch_event(request.model_dump(mode="json"))


def create_adaptive_profile_record(request: AdaptiveProfileRequest) -> dict[str, Any]:
    return persist_adaptive_profile(
        {
            "id": request.id,
            "market": request.market,
            "reward_definition_version": request.reward_definition_version,
            "state_definition_version": request.state_definition_version,
            "notes": request.notes,
        },
        {
            "id": f"{request.id}:{request.rollout_control_version}",
            "rollout_control_version": request.rollout_control_version,
            "mode": "shadow",
            "detail": request.rollout_detail,
        },
    )


def create_adaptive_training_run_record(
    request: AdaptiveTrainingRunRequest,
) -> dict[str, Any]:
    profile = get_adaptive_profile(request.adaptive_profile_id)
    profile_contract = {
        "reward_definition_version": profile["reward_definition_version"],
        "state_definition_version": profile["state_definition_version"],
        "rollout_control_version": profile["rollout_control_version"],
    }
    request_contract = {
        "reward_definition_version": request.reward_definition_version,
        "state_definition_version": request.state_definition_version,
        "rollout_control_version": request.rollout_control_version,
    }
    mismatches = [
        key
        for key, expected in profile_contract.items()
        if request_contract[key] != expected
    ]
    if mismatches:
        mismatch_text = ", ".join(sorted(mismatches))
        raise UnsupportedConfigurationError(
            "Adaptive training run contract must match the selected adaptive "
            f"profile. Mismatched fields: {mismatch_text}."
        )
    dataset_summary = {
        "builder": "research_run_registry_v1",
        "market": request.market,
        "run_id": request.run_id,
    }
    artifact_registry = {
        "trainer_interface_version": "adaptive_trainer_interface_v1",
        "profile_id": request.adaptive_profile_id,
    }
    return persist_adaptive_training_run(
        {
            "profile_id": request.adaptive_profile_id,
            "run_id": request.run_id,
            "market": request.market,
            "adaptive_mode": request.adaptive_mode,
            "reward_definition_version": request.reward_definition_version,
            "state_definition_version": request.state_definition_version,
            "rollout_control_version": request.rollout_control_version,
            "status": "validated",
            "dataset_summary": dataset_summary,
            "artifact_registry": artifact_registry,
            "validation_error": None,
        }
    )


def list_adaptive_profile_records(limit: int = 50) -> list[dict[str, Any]]:
    return list_adaptive_profiles(limit=limit)


def list_adaptive_training_run_records(limit: int = 50) -> list[dict[str, Any]]:
    return list_adaptive_training_runs(limit=limit)


def record_run_adaptive_exclusion(run_id: str) -> None:
    persist_adaptive_surface_exclusion(
        {
            "run_id": run_id,
            "exclusion_surface": "default_non_adaptive_surfaces",
            "reason": "adaptive run must remain isolated from default comparison and execution-ready views",
        }
    )


def list_kill_switch_records(limit: int = 20) -> list[dict[str, Any]]:
    return list_kill_switch_events(limit=limit)


def list_execution_readbacks(route: str, limit: int = 100) -> list[dict[str, Any]]:
    return list_execution_orders(route=route, limit=limit)


def list_adaptive_exclusion_records(limit: int = 100) -> list[dict[str, Any]]:
    return list_adaptive_surface_exclusions(limit=limit)
