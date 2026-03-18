from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Protocol

import pandas as pd

from .api_models import StrategyConfig
from .errors import UnsupportedConfigurationError

RUNTIME_COMPATIBILITY_MODE = "runtime_compatibility_mode"
VNEXT_SPEC_MODE = "vnext_spec_mode"
RESEARCH_SPEC_V1 = "research_spec_v1"
THRESHOLD_POLICY_VERSION = "static_absolute_gross_label_v1"
COMPARISON_ELIGIBILITY = "comparison_metadata_only"
PRICE_BASIS_VERSION_TEMPLATE = (
    "label_{return_target}__entry_ohlc_default__exit_ohlc_default__benchmark_unset_v1"
)
GROSS_LABEL_RETURN_TARGET = "open_to_open"


@dataclass(frozen=True)
class DefaultStrategyBundle:
    version: str
    threshold: float
    top_n: int


@dataclass(frozen=True)
class FallbackDecision:
    attempted: bool
    outcome: Literal["not_needed", "accepted", "rejected"]


@dataclass(frozen=True)
class ResearchStrategyConfig:
    type: str
    threshold: float
    top_n: int
    allow_proactive_sells: bool


class StrategyRunner(Protocol):
    strategy_type: str

    def build_weights(
        self,
        scores: pd.DataFrame,
        strategy: ResearchStrategyConfig,
    ) -> pd.DataFrame: ...


DEFAULT_STRATEGY_BUNDLES: Dict[str, DefaultStrategyBundle] = {
    RESEARCH_SPEC_V1: DefaultStrategyBundle(
        version=RESEARCH_SPEC_V1,
        threshold=0.01,
        top_n=10,
    ),
}


def build_weights_from_scores(
    scores: pd.DataFrame,
    threshold: float,
    top_n: int,
    allow_proactive_sells: bool,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    current_holdings: set[str] = set()

    for idx, row in scores.iterrows():
        row = row.dropna()
        eligible = row[row >= threshold]
        selected = eligible.nlargest(top_n).index.tolist()

        if allow_proactive_sells:
            holdings = selected
        else:
            current_holdings.update(selected)
            holdings = sorted(current_holdings)

        if not holdings:
            continue

        weight = 1.0 / len(holdings)
        weights.loc[idx, holdings] = weight

    return weights


class ResearchV1Runner:
    strategy_type = "research_v1"

    def build_weights(
        self,
        scores: pd.DataFrame,
        strategy: ResearchStrategyConfig,
    ) -> pd.DataFrame:
        return build_weights_from_scores(
            scores=scores,
            threshold=strategy.threshold,
            top_n=strategy.top_n,
            allow_proactive_sells=strategy.allow_proactive_sells,
        )


STRATEGY_RUNNERS: Dict[str, StrategyRunner] = {
    "research_v1": ResearchV1Runner(),
}


def resolve_strategy_config(strategy: StrategyConfig | ResearchStrategyConfig) -> ResearchStrategyConfig:
    return ResearchStrategyConfig(
        type=strategy.type,
        threshold=strategy.threshold,
        top_n=strategy.top_n,
        allow_proactive_sells=strategy.allow_proactive_sells,
    )


def resolve_runtime_strategy(
    strategy: StrategyConfig,
    runtime_mode: str,
    default_bundle_version: str | None,
) -> dict:
    if runtime_mode not in {RUNTIME_COMPATIBILITY_MODE, VNEXT_SPEC_MODE}:
        raise UnsupportedConfigurationError(f"Unsupported runtime mode '{runtime_mode}'.")

    threshold = strategy.threshold
    top_n = strategy.top_n

    threshold_fallback = FallbackDecision(attempted=False, outcome="not_needed")
    top_n_fallback = FallbackDecision(attempted=False, outcome="not_needed")

    bundle = None
    if default_bundle_version is not None:
        bundle = DEFAULT_STRATEGY_BUNDLES.get(default_bundle_version)
        if bundle is None:
            raise UnsupportedConfigurationError(
                f"Unsupported default bundle version '{default_bundle_version}'."
            )

    if runtime_mode == RUNTIME_COMPATIBILITY_MODE:
        if threshold is None:
            raise UnsupportedConfigurationError(
                "strategy.threshold is required in runtime_compatibility_mode."
            )
        if top_n is None:
            raise UnsupportedConfigurationError(
                "strategy.top_n is required in runtime_compatibility_mode."
            )
    else:
        if threshold is None:
            if bundle is None:
                raise UnsupportedConfigurationError(
                    "default_bundle_version is required when vnext_spec_mode uses spec defaults."
                )
            threshold = bundle.threshold
            threshold_fallback = FallbackDecision(attempted=True, outcome="accepted")
        if top_n is None:
            if bundle is None:
                raise UnsupportedConfigurationError(
                    "default_bundle_version is required when vnext_spec_mode uses spec defaults."
                )
            top_n = bundle.top_n
            top_n_fallback = FallbackDecision(attempted=True, outcome="accepted")

    config = ResearchStrategyConfig(
        type=strategy.type,
        threshold=threshold,
        top_n=top_n,
        allow_proactive_sells=strategy.allow_proactive_sells,
    )

    return {
        "strategy": config,
        "default_bundle_version": default_bundle_version,
        "config_sources": {
            "strategy": {
                "threshold": "request_override" if strategy.threshold is not None else "spec_default",
                "top_n": "request_override" if strategy.top_n is not None else "spec_default",
            }
        },
        "fallback_audit": {
            "strategy": {
                "threshold": {
                    "attempted": threshold_fallback.attempted,
                    "outcome": threshold_fallback.outcome,
                },
                "top_n": {
                    "attempted": top_n_fallback.attempted,
                    "outcome": top_n_fallback.outcome,
                },
            }
        },
    }


def build_threshold_policy_version(return_target: str) -> str | None:
    if return_target != GROSS_LABEL_RETURN_TARGET:
        return None
    return THRESHOLD_POLICY_VERSION


def build_price_basis_version(return_target: str) -> str | None:
    if return_target != GROSS_LABEL_RETURN_TARGET:
        return None
    return PRICE_BASIS_VERSION_TEMPLATE.format(return_target=return_target)


def get_strategy_runner(strategy_type: str) -> StrategyRunner:
    runner = STRATEGY_RUNNERS.get(strategy_type)
    if runner is None:
        raise UnsupportedConfigurationError(
            f"Unsupported strategy type '{strategy_type}'."
        )
    return runner
