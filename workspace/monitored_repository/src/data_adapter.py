"""Provider boundary: local data today, GitHub/API adapters can be attached later."""

def normalize(candle):
    return {
        "open": float(candle["open"]),
        "high": float(candle["high"]),
        "low": float(candle["low"]),
        "close": float(candle["close"]),
        "volume": int(candle.get("volume", 0)),
    }
