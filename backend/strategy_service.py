from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

import pandas as pd

from .errors import UnsupportedConfigurationError


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
    ) -> pd.DataFrame:
        ...


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


def resolve_strategy_config(strategy: object) -> ResearchStrategyConfig:
    return ResearchStrategyConfig(
        type=strategy.type,
        threshold=strategy.threshold,
        top_n=strategy.top_n,
        allow_proactive_sells=strategy.allow_proactive_sells,
    )


def get_strategy_runner(strategy_type: str) -> StrategyRunner:
    runner = STRATEGY_RUNNERS.get(strategy_type)
    if runner is None:
        raise UnsupportedConfigurationError(
            f"Unsupported strategy type '{strategy_type}'."
        )
    return runner
