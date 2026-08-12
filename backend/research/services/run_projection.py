from __future__ import annotations

from typing import Any

from backend.research.contracts.runs import (
    ComparisonCaveat,
    OpinionArtifact,
    ResearchRunCreateRequest,
    ResearchRunResponse,
    ValidationSummary,
)
from backend.research.domain.artifact_summary import (
    build_review_artifact_summary,
    has_requested_baselines,
)
from backend.research.domain.opinion import build_opinion_artifact
from backend.research.domain.result_caveats import warnings_with_result_caveats
from backend.research.domain.version_pack import build_version_pack_payload
from backend.research.repositories.runs import (
    get_research_run_snapshot,
    list_research_run_snapshots,
)


def _validation_summary_from_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if "method" not in value or "metrics" not in value:
        return None
    if not isinstance(value["metrics"], dict):
        return None
    payload = dict(value)
    if "evaluation_status" not in payload:
        if payload["metrics"]:
            payload["evaluation_status"] = "evaluated"
        else:
            payload["evaluation_status"] = "not_evaluated"
            payload["status_reason"] = (
                "Legacy validation record has no metrics or persisted status reason."
            )
    try:
        return ValidationSummary.model_validate(payload).model_dump(mode="json")
    except ValueError:
        return None


def _direction_diagnostics_from_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("task") != "binary_classification":
        return None
    if value.get("evaluation_status") not in {"evaluated", "not_evaluated"}:
        return None
    payload = {
        "task": "binary_classification",
        "evaluation_status": value["evaluation_status"],
        "status_reason": value.get("status_reason"),
        "sample_count": value.get("sample_count", 0),
        "positive_return_threshold": value.get("positive_return_threshold", 0.0),
        "confirmation_probability_threshold": value.get(
            "confirmation_probability_threshold", 0.5
        ),
        "calibration_method": value.get("calibration_method", "sigmoid"),
        "calibration_policy_version": value.get(
            "calibration_policy_version",
            "chronological_tail_20pct_min20_class5_v1",
        ),
        "confirmation_policy_version": value.get(
            "confirmation_policy_version",
            "regression_threshold_direction_probability_v1",
        ),
        "calibration_sample_count": value.get("calibration_sample_count", 0),
        "positive_prevalence": value.get("positive_prevalence"),
        "confusion_matrix": value.get("confusion_matrix", []),
        "precision": value.get("precision"),
        "recall": value.get("recall"),
        "roc_auc": value.get("roc_auc"),
        "pr_auc": value.get("pr_auc"),
        "brier": value.get("brier"),
    }
    for key in (
        "sample_count",
        "positive_return_threshold",
        "confirmation_probability_threshold",
        "calibration_sample_count",
        "positive_prevalence",
        "precision",
        "recall",
        "roc_auc",
        "pr_auc",
        "brier",
    ):
        if payload[key] is not None and not isinstance(payload[key], int | float):
            return None
    if not isinstance(payload["confusion_matrix"], list):
        return None
    return payload


def _model_diagnostics_from_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("task") != "regression":
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
        "direction_classification": _direction_diagnostics_from_payload(
            value.get("direction_classification")
        ),
    }
    for key in ("rmse", "mae", "rank_ic", "linear_ic"):
        if payload[key] is not None and not isinstance(payload[key], int | float):
            payload[key] = None
    for key in ("actual_vs_predicted", "residuals", "feature_importance"):
        if not isinstance(payload[key], list):
            payload[key] = []
    return payload


def _summarize_model_diagnostics(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {
        **payload,
        "actual_vs_predicted": [],
        "residuals": [],
        "feature_importance": [],
    }


def _project_reviewable_payload(
    payload: dict[str, Any],
    *,
    artifact_presence: dict[str, bool],
    summary_only: bool,
) -> dict[str, Any]:
    projected = dict(payload)
    summary = build_review_artifact_summary(
        status=str(projected.get("status") or ""),
        request_payload=projected.get("request_payload"),
        comparison_eligibility=projected.get("comparison_eligibility"),
        artifact_presence=artifact_presence,
        market=projected.get("market"),
    )
    projected.update(summary)
    projected["opinion_artifact"] = build_opinion_artifact(
        {**projected, "summary_only": summary_only}
    )
    return projected


def project_live_response(
    response: ResearchRunResponse,
    request: ResearchRunCreateRequest,
) -> ResearchRunResponse:
    request_payload = request.model_dump(mode="json")
    payload = {
        **response.model_dump(mode="json", exclude={"opinion_artifact"}),
        "status": "succeeded",
        "request_payload": request_payload,
    }
    payload["warnings"] = warnings_with_result_caveats(
        payload.get("warnings"),
        status="succeeded",
        market=payload.get("market"),
        request_payload=request_payload,
    )
    projected = _project_reviewable_payload(
        payload,
        artifact_presence={
            "metrics": True,
            "model_diagnostics": response.model_diagnostics is not None,
            "equity_curve": True,
            "signals": True,
            "validation": response.validation is not None,
            "baselines": has_requested_baselines(
                request_payload,
                response.baselines,
            ),
        },
        summary_only=False,
    )
    return response.model_copy(
        update={
            "artifact_completeness": projected["artifact_completeness"],
            "present_artifacts": projected["present_artifacts"],
            "missing_artifacts": projected["missing_artifacts"],
            "not_required_artifacts": projected["not_required_artifacts"],
            "comparison_caveats": [
                ComparisonCaveat.model_validate(item)
                for item in projected["comparison_caveats"]
            ],
            "warnings": projected["warnings"],
            "opinion_artifact": OpinionArtifact.model_validate(
                projected["opinion_artifact"]
            ),
        }
    )


def project_persisted_snapshot(
    snapshot: dict[str, Any],
    *,
    include_artifacts: bool,
) -> dict[str, Any]:
    payload = dict(snapshot)
    required_metadata_keys = (
        "_artifact_presence",
        "_version_pack_values",
        "_raw_model_diagnostics",
    )
    missing_metadata_keys = [
        key for key in required_metadata_keys if key not in payload
    ]
    if missing_metadata_keys:
        raise ValueError(
            "Persisted research run snapshot is missing required metadata keys: "
            + ", ".join(missing_metadata_keys)
        )
    artifact_presence = dict(payload.pop("_artifact_presence"))
    version_pack_values = payload.pop("_version_pack_values")
    raw_model_diagnostics = payload.pop("_raw_model_diagnostics")
    validation_outcome = payload.get("validation_outcome")
    payload["validation"] = _validation_summary_from_payload(validation_outcome)
    parsed_model_diagnostics = _model_diagnostics_from_payload(raw_model_diagnostics)
    payload["model_diagnostics"] = (
        parsed_model_diagnostics
        if include_artifacts
        else _summarize_model_diagnostics(parsed_model_diagnostics)
    )
    artifact_presence["model_diagnostics"] = parsed_model_diagnostics is not None
    artifact_presence["validation"] = payload["validation"] is not None
    artifact_presence["baselines"] = bool(artifact_presence["baselines"]) and (
        has_requested_baselines(
            payload.get("request_payload"),
            payload.get("baselines"),
        )
    )
    payload.update(build_version_pack_payload(version_pack_values))
    return _project_reviewable_payload(
        payload,
        artifact_presence=artifact_presence,
        summary_only=not include_artifacts,
    )


def get_research_run_record(run_id: str) -> dict[str, Any]:
    return project_persisted_snapshot(
        get_research_run_snapshot(run_id),
        include_artifacts=True,
    )


def list_research_run_records(limit: int = 20) -> list[dict[str, Any]]:
    return [
        project_persisted_snapshot(snapshot, include_artifacts=False)
        for snapshot in list_research_run_snapshots(limit=limit)
    ]
