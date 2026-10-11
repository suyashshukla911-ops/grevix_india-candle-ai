
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import quote_plus

import requests


POS = {
    "beat", "beats", "beating", "growth", "profit", "profits", "surge", "surges", "rally",
    "rallies", "rise", "rises", "rising", "gain", "gains", "strong", "upgrade", "upgraded",
    "outperform", "record", "boost", "boosted", "approval", "approved", "contract", "deal",
    "partnership", "launch", "launched", "expansion", "demand", "recovery", "acquire",
    "acquisition", "buyback", "dividend", "order", "orders", "guidance", "optimistic",
}
NEG = {
    "miss", "missed", "loss", "losses", "fall", "falls", "drop", "drops", "decline", "declined",
    "plunge", "plunged", "crash", "down", "weak", "downgrade", "downgraded", "underperform",
    "lawsuit", "investigation", "fraud", "scandal", "default", "debt", "warning", "penalty",
    "fine", "layoff", "layoffs", "delay", "delayed", "recall", "probe", "resign", "resignation",
    "cut", "cuts", "regulatory", "ban", "strike", "fire", "slump", "concern",
}

EVENT_WEIGHTS = {
    "earnings": 1.00,
    "guidance": 0.95,
    "m&a": 0.90,
    "contract": 0.75,
    "regulatory": 0.90,
    "litigation": 0.90,
    "management": 0.65,
    "capital": 0.75,
    "product": 0.45,
    "operations": 0.45,
    "macro": 0.55,
    "analyst": 0.35,
    "other": 0.20,
}

SOURCE_WEIGHTS = {
    "reuters.com": 1.00,
    "economictimes.indiatimes.com": 0.95,
    "moneycontrol.com": 0.90,
    "business-standard.com": 0.90,
    "livemint.com": 0.90,
    "financialexpress.com": 0.85,
    "timesofindia.indiatimes.com": 0.80,
}

EVENT_PATTERNS = {
    "earnings": [r"\bresults?\b", r"\bprofit\b", r"\brevenue\b", r"\bearnings?\b", r"\bq[1-4]\b"],
    "guidance": [r"\bguidance\b", r"\boutlook\b", r"\bforecast\b", r"\bexpects?\b", r"\btarget\b"],
    "m&a": [r"\bacqui(?:re|red|res|sition)\b", r"\bmerger\b", r"\btakeover\b", r"\bstake\b"],
    "contract": [r"\border\b", r"\bcontract\b", r"\bdeal\b", r"\bwon\b", r"\baward\b"],
    "regulatory": [r"\bsebi\b", r"\brbi\b", r"\bregulator\b", r"\bpenalty\b", r"\bban\b", r"\bapproval\b"],
    "litigation": [r"\blawsuit\b", r"\bprobe\b", r"\binvestigation\b", r"\bfraud\b", r"\bscandal\b"],
    "management": [r"\bceo\b", r"\bmd\b", r"\bchairman\b", r"\bresign\b", r"\bresignation\b", r"\bappoints?\b"],
    "capital": [r"\bdividend\b", r"\bbuyback\b", r"\bfund[- ]?raise\b", r"\bdebt\b", r"\bcapital\b"],
    "product": [r"\blaunch\b", r"\bproduct\b", r"\bnew model\b", r"\bplatform\b"],
    "operations": [r"\bplant\b", r"\bshutdown\b", r"\bproduction\b", r"\bcapacity\b", r"\bstrike\b"],
    "macro": [r"\binflation\b", r"\brates?\b", r"\boil prices?\b", r"\brupee\b", r"\btariff\b", r"\bgdp\b"],
    "analyst": [r"\bupgrade\b", r"\bdowngrade\b", r"\bbroker\b", r"\bprice target\b", r"\banalyst\b"],
}


def lexical_sentiment(text: str) -> float:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]*", text.lower())
    pos = sum(w in POS for w in words)
    neg = sum(w in NEG for w in words)
    total = pos + neg
    return 0.0 if total == 0 else round((pos - neg) / total, 3)


def classify_event(text: str) -> tuple[str, float]:
    low = text.lower()
    for event, patterns in EVENT_PATTERNS.items():
        if any(re.search(p, low) for p in patterns):
            return event, EVENT_WEIGHTS.get(event, 0.2)
    return "other", EVENT_WEIGHTS["other"]


def source_weight(domain: str) -> float:
    d = domain.lower().replace("www.", "")
    for source, weight in SOURCE_WEIGHTS.items():
        if d.endswith(source):
            return weight
    return 0.65


class NewsService:
    def __init__(self, max_records: int = 50):
        self.max_records = max_records
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "IndiaCandleAI/1.0"})

    def _gdelt(self, query: str, timespan: str = "24h") -> list[dict]:
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "timespan": timespan,
            "maxrecords": min(self.max_records, 250),
            "sort": "datedesc",
        }
        response = self.session.get(url, params=params, timeout=25)
        if response.status_code >= 400:
            return []
        try:
            payload = response.json()
        except Exception:
            return []
        return payload.get("articles", []) or []

    def search(self, company: str, symbol: str, timespan: str = "24h") -> list[dict]:
        # GDELT searches indexed worldwide news. The sourcecountry filter keeps the core
        # search focused on Indian coverage, while the second query picks up major global
        # stories that mention the company.
        q1 = f'"{company}" sourcecountry:IN'
        q2 = f'("{company}" OR "{symbol}") (business OR finance OR market OR technology)'
        raw = self._gdelt(q1, timespan=timespan) + self._gdelt(q2, timespan=timespan)

        seen = set()
        scored = []
        now = datetime.now(timezone.utc)

        for a in raw:
            url = a.get("url") or ""
            title = (a.get("title") or "").strip()
            if not title or not url or url in seen:
                continue
            seen.add(url)

            tone = lexical_sentiment(title)
            event, event_weight = classify_event(title)
            domain = a.get("domain") or "unknown"
            sw = source_weight(domain)

            seendate = a.get("seendate") or ""
            age_hours = 24.0
            try:
                ts = datetime.strptime(seendate[:14], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                age_hours = max(0.0, (now - ts).total_seconds() / 3600)
            except Exception:
                pass
            recency = math.exp(-age_hours / 18.0)

            # Impact is deliberately capped. News is a risk/signal modifier, not a magic
            # "predict the exact price" component.
            impact = max(-1.0, min(1.0, tone * event_weight * sw * (0.5 + 0.5 * recency)))
            scored.append({
                "title": title,
                "url": url,
                "domain": domain,
                "seendate": seendate,
                "sentiment": tone,
                "event": event,
                "impact": round(impact, 4),
                "recency": round(recency, 4),
            })

        scored.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return scored[: self.max_records]

    @staticmethod
    def aggregate(articles: Iterable[dict]) -> dict:
        articles = list(articles)
        if not articles:
            return {
                "headline_count": 0,
                "sentiment": 0.0,
                "impact": 0.0,
                "positive": 0,
                "negative": 0,
                "neutral": 0,
                "top_event": "none",
            }
        impacts = [a["impact"] for a in articles]
        sentiments = [a["sentiment"] for a in articles]
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        event_scores = {}
        for a in articles:
            label = "positive" if a["sentiment"] > 0.15 else "negative" if a["sentiment"] < -0.15 else "neutral"
            counts[label] += 1
            event_scores[a["event"]] = event_scores.get(a["event"], 0.0) + abs(a["impact"])
        top_event = max(event_scores, key=event_scores.get) if event_scores else "none"
        return {
            "headline_count": len(articles),
            "sentiment": round(sum(sentiments) / len(sentiments), 4),
            "impact": round(sum(impacts) / len(impacts), 4),
            **counts,
            "top_event": top_event,
        }
