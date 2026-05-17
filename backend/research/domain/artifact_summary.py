from __future__ import annotations

from typing import Any, Literal

ReviewArtifactName = Literal[
    "metrics",
    "model_diagnostics",
    "equity_curve",
    "signals",
    "validation",
    "baselines",
]
ArtifactCompleteness = Literal["complete", "partial", "metadata_only"]
ComparisonCaveatSeverity = Literal["blocker", "note"]

CORE_REVIEW_ARTIFACTS: tuple[ReviewArtifactName, ...] = (
    "metrics",
    "model_diagnostics",
    "equity_curve",
    "signals",
)
CONDITIONAL_REVIEW_ARTIFACTS: tuple[ReviewArtifactName, ...] = (
    "validation",
    "baselines",
)
REVIEW_ARTIFACTS: tuple[ReviewArtifactName, ...] = (
    *CORE_REVIEW_ARTIFACTS,
    *CONDITIONAL_REVIEW_ARTIFACTS,
)
SUCCESS_STATUS = "succeeded"


def _requests_validation(request_payload: dict[str, Any] | None) -> bool | None:
    if request_payload is None:
        return None
    return request_payload.get("validation") is not None


def _requests_baselines(request_payload: dict[str, Any] | None) -> bool | None:
    if request_payload is None:
        return None
    baselines = request_payload.get("baselines")
    return isinstance(baselines, list) and len(baselines) > 0


def _required_artifacts(
    request_payload: dict[str, Any] | None,
) -> tuple[ReviewArtifactName, ...]:
    required = list(CORE_REVIEW_ARTIFACTS)
    validation_requested = _requests_validation(request_payload)
    baselines_requested = _requests_baselines(request_payload)

    if validation_requested is not False:
        required.append("validation")
    if baselines_requested is not False:
        required.append("baselines")
    return tuple(required)


def _not_required_artifacts(
    request_payload: dict[str, Any] | None,
) -> tuple[ReviewArtifactName, ...]:
    not_required: list[ReviewArtifactName] = []
    if _requests_validation(request_payload) is False:
        not_required.append("validation")
    if _requests_baselines(request_payload) is False:
        not_required.append("baselines")
    return tuple(not_required)


def _comparison_caveat(
    code: str,
    label: str,
    severity: ComparisonCaveatSeverity = "blocker",
) -> dict[str, str]:
    return {"code": code, "label": label, "severity": severity}


def build_review_artifact_summary(
    *,
    status: str | None,
    request_payload: dict[str, Any] | None,
    artifact_presence: dict[ReviewArtifactName, bool],
    comparison_eligibility: str | None,
) -> dict[str, Any]:
    required_artifacts = _required_artifacts(request_payload)
    not_required_artifacts = list(_not_required_artifacts(request_payload))
    present_artifacts = [
        artifact
        for artifact in REVIEW_ARTIFACTS
        if artifact_presence.get(artifact) and artifact not in not_required_artifacts
    ]
    missing_artifacts = [
        artifact
        for artifact in required_artifacts
        if not artifact_presence.get(artifact)
    ]
    present_required_artifacts = [
        artifact
        for artifact in required_artifacts
        if artifact_presence.get(artifact)
    ]

    if not missing_artifacts:
        completeness: ArtifactCompleteness = "complete"
    elif present_required_artifacts:
        completeness = "partial"
    else:
        completeness = "metadata_only"

    caveats: list[dict[str, str]] = []
    if status != SUCCESS_STATUS:
        caveats.append(
            _comparison_caveat(
                "ARTIFACTS_NOT_EVALUATED",
                "Review artifacts were not evaluated for this run status.",
            )
        )
    if completeness == "metadata_only":
        caveats.append(
            _comparison_caveat(
                "METADATA_ONLY_RECORD",
                "Saved record has metadata only.",
            )
        )
    elif completeness == "partial":
        caveats.append(
            _comparison_caveat(
                "REVIEW_ARTIFACTS_MISSING",
                "Review artifacts are missing.",
            )
        )

    if comparison_eligibility == "comparison_metadata_only":
        caveats.append(
            _comparison_caveat(
                "COMPARISON_METADATA_ONLY",
                "Comparison metadata is incomplete.",
            )
        )
    elif comparison_eligibility == "sample_window_pending":
        caveats.append(
            _comparison_caveat(
                "SAMPLE_WINDOW_PENDING",
                "Sample window is pending.",
            )
        )
    elif comparison_eligibility == "unresolved_event_quarantine":
        caveats.append(
            _comparison_caveat(
                "UNRESOLVED_EVENT_QUARANTINE",
                "Corporate-event data is unresolved.",
            )
        )
    elif comparison_eligibility is None:
        caveats.append(
            _comparison_caveat(
                "COMPARISON_ELIGIBILITY_UNAVAILABLE",
                "Comparison eligibility is unavailable.",
            )
        )

    return {
        "artifact_completeness": completeness,
        "present_artifacts": present_artifacts,
        "missing_artifacts": missing_artifacts,
        "not_required_artifacts": not_required_artifacts,
        "comparison_caveats": caveats,
    }
