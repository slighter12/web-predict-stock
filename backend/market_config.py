DEFAULT_MARKET_CONFIG = {
    "TW": {
        "execution": {
            "fees": 0.002,
            "slippage": 0.001,
        },
    },
    "US": {
        "execution": {
            "fees": 0.0005,
            "slippage": 0.0005,
        },
    },
}


def get_market_config(market: str) -> dict:
    market_key = (market or "").upper()
    return DEFAULT_MARKET_CONFIG.get(market_key, DEFAULT_MARKET_CONFIG["TW"])
