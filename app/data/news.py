from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

POSITIVE = {"growth","profit","profits","surge","rise","rises","rising","gain","gains","positive","strong","record","upgrade","buy","bullish","success","expansion","deal","contract","approval","revenue","increase","beat","outperform","recovery","innovation","launch","partnership","investment","demand"}
NEGATIVE = {"loss","losses","fall","falls","falling","drop","drops","decline","declining","negative","weak","downgrade","sell","bearish","risk","risks","lawsuit","investigation","fraud","scandal","debt","default","warning","cut","layoff","crisis","delay","miss","underperform","regulatory","penalty","fine","concern"}

class NewsService:
    def __init__(self):
        self._cache: dict[str, tuple[float,list[dict[str,Any]]]] = {}

    @staticmethod
    def score_text(text:str)->float:
        words=re.findall(r"[a-zA-Z]+",(text or "").lower())
        pos=sum(w in POSITIVE for w in words); neg=sum(w in NEGATIVE for w in words); total=pos+neg
        return 0.0 if total==0 else (pos-neg)/total

    @staticmethod
    def _age_hours(value:Any)->float:
        if value is None: return 999.0
        try:
            if isinstance(value,(int,float)):
                dt=datetime.fromtimestamp(value,tz=timezone.utc)
            else:
                raw=str(value).replace("Z","+00:00")
                dt=datetime.fromisoformat(raw)
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            return max(0.0,(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/3600)
        except Exception:
            return 999.0

    def fetch(self,symbol:str,company_name:str,limit:int=8)->list[dict[str,Any]]:
        key=f"{symbol}|{company_name}"
        now=time.time()
        hit=self._cache.get(key)
        if hit and now-hit[0]<300: return hit[1][:limit]
        items=[]
        try:
            import yfinance as yf
            ticker=yf.Ticker(symbol if "." in symbol or symbol.startswith("^") else f"{symbol}.NS")
            raw=getattr(ticker,"news",None)
            if callable(raw): raw=raw()
            for item in (raw or [])[:max(limit,12)]:
                content=item.get("content") or {}
                title=content.get("title") or item.get("title")
                if not title: continue
                published=content.get("pubDate") or item.get("providerPublishTime")
                age=self._age_hours(published)
                if age>72: continue
                base=self.score_text(title)
                # Recent headlines carry more weight; old headlines decay smoothly.
                weight=max(0.2, 1/(1+age/12))
                publisher=content.get("provider",{}).get("displayName") if isinstance(content.get("provider"),dict) else item.get("publisher","")
                url=(content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"),dict) else item.get("link","")
                items.append({"title":title,"publisher":publisher or "Yahoo Finance","url":url or "",
                              "published":published,"age_hours":round(age,2),"sentiment":round(base,3),
                              "impact":round(base*weight,3)})
        except Exception:
            items=[]
        self._cache[key]=(now,items)
        return items[:limit]

    def aggregate(self,articles:list[dict[str,Any]])->dict[str,Any]:
        if not articles:
            return {"headline_count":0,"positive":0,"negative":0,"neutral":0,"impact":0.0,"status":"UNAVAILABLE"}
        scores=[float(x.get("impact",0.0)) for x in articles]
        return {"headline_count":len(articles),"positive":sum(1 for x in scores if x>0.15),
                "negative":sum(1 for x in scores if x<-0.15),
                "neutral":sum(1 for x in scores if -0.15<=x<=0.15),
                "impact":round(max(-1,min(1,sum(scores)/len(scores))),3),
                "status":"LIVE"}
