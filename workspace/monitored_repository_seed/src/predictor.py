"""Core model scoring path for the stock prediction workspace."""

def score(features, threshold=0.65):
    probability = float(features.get("probability", 0.5))
    if probability >= threshold:
        return "BUY"
    if probability <= 1 - threshold:
        return "SELL"
    return "NO-TRADE"
