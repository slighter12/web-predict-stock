import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def load_env(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env(Path(".env"))

from backend.api_models import BacktestRequest
from backend.main import run_backtest_endpoint


def main() -> None:

    request = BacktestRequest(
        market="TW",
        symbols=["2330"],
        date_range={"start": "2022-01-01", "end": "2024-01-01"},
        return_target="open_to_open",
        horizon_days=1,
        features=[
            {"name": "ma", "window": 5, "source": "close", "shift": 1},
            {"name": "rsi", "window": 14, "source": "close", "shift": 1},
        ],
        model={"type": "xgboost", "params": {}},
        selection={
            "threshold_metric": "predicted_return",
            "threshold": 0.003,
            "top_n": 5,
            "weighting": "equal",
        },
        trading_rules={
            "rebalance": "daily_open",
            "allow_same_day_reinvest": True,
            "allow_intraday": False,
            "allow_leverage": False,
        },
        exit_rules={
            "allow_proactive_sells": True,
            "default_liquidation": "next_open",
        },
        execution={
            "matching_model": "ohlc_default",
            "slippage": 0.001,
            "fees": 0.002,
        },
        validation={"method": "walk_forward", "splits": 2, "test_size": 0.2},
        baselines=["buy_and_hold", "naive_momentum"],
    )

    result = run_backtest_endpoint(request)
    payload = result.model_dump()

    print(
        {
            "run_id": payload["run_id"],
            "metrics": payload["metrics"],
            "equity_points": len(payload["equity_curve"]),
            "signals": len(payload["signals"]),
            "baselines": payload["baselines"],
            "validation": payload["validation"],
            "warnings": payload["warnings"],
        }
    )


if __name__ == "__main__":
    main()
