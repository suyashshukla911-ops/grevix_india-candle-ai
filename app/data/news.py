
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import requests

POSITIVE = {
    "growth","profit","profits","surge","rise","rises","rising","gain","gains",
    "positive","strong","record","upgrade","buy","bullish","success","expansion",
    "deal","contract","approval","revenue","increase","beat","outperform",
    "recovery","innovation","launch","partnership","investment","demand"
}
NEGATIVE = {
    "loss","losses","fall","falls","falling","drop","drops","decline","declining",
    "negative","weak","downgrade","sell","bearish","risk","risks","lawsuit",
    "investigation","fraud","scandal","debt","default","warning","cut","layoff",
    "crisis","delay","miss","underperform","regulatory","penalty","fine","concern"
}

class NewsService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "IndiaCandleAI/TrustGraph"})

    @staticmethod
    def score_text(text: str) -> float:
        words = re.findall(r"[a-zA-Z]+", (text or "").lower())
        pos = sum(w in POSITIVE for w in words)
        neg = sum(w in NEGATIVE for w in words)
        total = pos + neg
        return 0.0 if total == 0 else (pos - neg) / total

    def fetch(self, symbol: str, company_name: str, limit: int = 8) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol if "." in symbol or symbol.startswith("^") else f"{symbol}.NS")
            raw = getattr(ticker, "news", None)
            if callable(raw):
                raw = raw()
            for item in (raw or [])[:limit]:
                content = item.get("content") or {}
                title = content.get("title") or item.get("title") or "Market update"
                score = self.score_text(title)
                items.append({
                    "title": title,
                    "publisher": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else item.get("publisher", "Yahoo Finance"),
                    "url": (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link", ""),
                    "published": content.get("pubDate") or item.get("providerPublishTime"),
                    "sentiment": round(score, 3),
                    "impact": round(score, 3),
                })
        except Exception:
            pass
        if not items:
            # Deterministic, clearly labeled local context. It is not presented as live news.
            items = [
                {"title": f"{company_name}: local market context available", "publisher": "Local fallback",
                 "url": "", "published": datetime.now().isoformat(), "sentiment": 0.0, "impact": 0.0},
            ]
        return items

    def aggregate(self, articles: list[dict[str, Any]]) -> dict[str, Any]:
        scores = [float(x.get("sentiment", 0.0)) for x in articles]
        impact = sum(scores) / max(len(scores), 1)
        return {
            "headline_count": len(articles),
            "positive": sum(1 for x in scores if x > 0.15),
            "negative": sum(1 for x in scores if x < -0.15),
            "neutral": sum(1 for x in scores if -0.15 <= x <= 0.15),
            "impact": round(max(-1.0, min(1.0, impact)), 3),
            "source": "Yahoo Finance when available; local fallback otherwise",
        }
