import pandas as pd

PRICE_COLS = ["open", "high", "low", "close"]


def apply_price_adjustment(
    frame: pd.DataFrame, factor_col: str = "adjust_factor"
) -> pd.DataFrame:
    """Return a copy with adjusted OHLC columns when an adjustment factor exists."""
    if frame.empty or factor_col not in frame.columns:
        return frame

    adjusted = frame.copy()
    factor = pd.to_numeric(adjusted[factor_col], errors="coerce")
    for column in PRICE_COLS:
        adjusted[f"{column}_adj"] = adjusted[column] * factor
    return adjusted
