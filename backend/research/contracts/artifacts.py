from typing import Literal

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
