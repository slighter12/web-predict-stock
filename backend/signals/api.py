from __future__ import annotations

from fastapi import APIRouter, Query

from backend.signals.contracts.clusters import (
    ClusterSnapshotRequest,
    ClusterSnapshotResponse,
)
from backend.signals.contracts.external_signals import (
    ExternalRawArchiveResponse,
    ExternalSignalAuditRequest,
    ExternalSignalAuditResponse,
    ExternalSignalIngestionRequest,
    ExternalSignalRecordResponse,
)
from backend.signals.contracts.factor_catalogs import (
    FactorCatalogRequest,
    FactorCatalogResponse,
    FactorMaterializationResponse,
)
from backend.signals.contracts.peer_features import (
    PeerFeatureRunRequest,
    PeerFeatureRunResponse,
)
from backend.signals.services.clusters import (
    create_cluster_snapshot,
    list_cluster_snapshot_records,
)
from backend.signals.services.external_signals import (
    create_external_signal_audit,
    create_external_signal_ingestion,
    list_external_signal_audit_runs,
    list_external_signals,
)
from backend.signals.services.factor_catalogs import (
    create_factor_catalog,
    list_factor_catalog_records,
    list_factor_materialization_records,
)
from backend.signals.services.peer_features import (
    create_peer_feature_run,
    list_peer_feature_run_records,
)

router = APIRouter()


@router.post(
    "/api/v1/data/external-signal-ingestions",
    tags=["Data Plane"],
    response_model=ExternalRawArchiveResponse,
)
def create_external_signal_ingestion_endpoint(
    request: ExternalSignalIngestionRequest,
) -> ExternalRawArchiveResponse:
    return ExternalRawArchiveResponse(**create_external_signal_ingestion(request))


@router.get(
    "/api/v1/data/external-signals",
    tags=["Data Plane"],
    response_model=list[ExternalSignalRecordResponse],
)
def read_external_signals() -> list[ExternalSignalRecordResponse]:
    return [ExternalSignalRecordResponse(**item) for item in list_external_signals()]


@router.post(
    "/api/v1/data/external-signal-audits",
    tags=["Data Plane"],
    response_model=ExternalSignalAuditResponse,
)
def create_external_signal_audit_endpoint(
    request: ExternalSignalAuditRequest,
) -> ExternalSignalAuditResponse:
    return ExternalSignalAuditResponse(**create_external_signal_audit(request))


@router.get(
    "/api/v1/data/external-signal-audits",
    tags=["Data Plane"],
    response_model=list[ExternalSignalAuditResponse],
)
def read_external_signal_audits() -> list[ExternalSignalAuditResponse]:
    return [
        ExternalSignalAuditResponse(**item)
        for item in list_external_signal_audit_runs()
    ]


@router.post(
    "/api/v1/data/factor-catalogs",
    tags=["Data Plane"],
    response_model=FactorCatalogResponse,
)
def create_factor_catalog_endpoint(
    request: FactorCatalogRequest,
) -> FactorCatalogResponse:
    return FactorCatalogResponse(**create_factor_catalog(request))


@router.get(
    "/api/v1/data/factor-catalogs",
    tags=["Data Plane"],
    response_model=list[FactorCatalogResponse],
)
def read_factor_catalogs() -> list[FactorCatalogResponse]:
    return [FactorCatalogResponse(**item) for item in list_factor_catalog_records()]


@router.get(
    "/api/v1/data/factor-materializations",
    tags=["Data Plane"],
    response_model=list[FactorMaterializationResponse],
)
def read_factor_materializations(
    run_id: str | None = Query(default=None),
) -> list[FactorMaterializationResponse]:
    return [
        FactorMaterializationResponse(**item)
        for item in list_factor_materialization_records(run_id=run_id)
    ]


@router.post(
    "/api/v1/data/cluster-snapshots",
    tags=["Data Plane"],
    response_model=ClusterSnapshotResponse,
)
def create_cluster_snapshot_endpoint(
    request: ClusterSnapshotRequest,
) -> ClusterSnapshotResponse:
    return ClusterSnapshotResponse(**create_cluster_snapshot(request))


@router.get(
    "/api/v1/data/cluster-snapshots",
    tags=["Data Plane"],
    response_model=list[ClusterSnapshotResponse],
)
def read_cluster_snapshots() -> list[ClusterSnapshotResponse]:
    return [ClusterSnapshotResponse(**item) for item in list_cluster_snapshot_records()]


@router.post(
    "/api/v1/data/peer-feature-runs",
    tags=["Data Plane"],
    response_model=PeerFeatureRunResponse,
)
def create_peer_feature_run_endpoint(
    request: PeerFeatureRunRequest,
) -> PeerFeatureRunResponse:
    return PeerFeatureRunResponse(**create_peer_feature_run(request))


@router.get(
    "/api/v1/data/peer-feature-runs",
    tags=["Data Plane"],
    response_model=list[PeerFeatureRunResponse],
)
def read_peer_feature_runs() -> list[PeerFeatureRunResponse]:
    return [PeerFeatureRunResponse(**item) for item in list_peer_feature_run_records()]
