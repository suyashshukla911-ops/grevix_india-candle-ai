
from __future__ import annotations

import gzip
import io
import json
import secrets
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode

import pandas as pd
import requests


UPSTOX_API = "https://api.upstox.com"
INSTRUMENT_URLS = {
    "NSE": "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz",
    "BSE": "https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz",
}


@dataclass
class Instrument:
    instrument_key: str
    exchange: str
    segment: str
    instrument_type: str
    name: str
    trading_symbol: str
    short_name: str
    isin: str = ""


class UpstoxError(RuntimeError):
    pass


class UpstoxClient:
    def __init__(self, access_token: str = "", cache_dir: str = "data_cache"):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "IndiaCandleAI/1.0",
        })
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._instruments: list[Instrument] | None = None

    def set_access_token(self, token: str) -> None:
        self.access_token = token.strip()

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            raise UpstoxError("Upstox is not connected. Set UPSTOX_ACCESS_TOKEN or use Connect Upstox.")
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    def _get_json(self, url: str, params: Optional[dict] = None) -> dict:
        response = self.session.get(url, headers=self._headers(), params=params, timeout=25)
        if response.status_code >= 400:
            raise UpstoxError(f"Upstox HTTP {response.status_code}: {response.text[:400]}")
        try:
            return response.json()
        except Exception as exc:
            raise UpstoxError("Upstox returned a non-JSON response.") from exc

    # ---------- OAuth ----------

    def authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{UPSTOX_API}/v2/login/authorization/dialog?{urlencode(params)}"

    def exchange_code(self, code: str, client_id: str, client_secret: str, redirect_uri: str) -> str:
        response = self.session.post(
            f"{UPSTOX_API}/v2/login/authorization/token",
            headers={"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=25,
        )
        if response.status_code >= 400:
            raise UpstoxError(f"OAuth token exchange failed ({response.status_code}): {response.text[:400]}")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise UpstoxError("OAuth response did not contain access_token.")
        self.set_access_token(token)
        return token

    # ---------- Instruments ----------

    def _download_instruments(self) -> list[Instrument]:
        rows: list[Instrument] = []
        for exchange, url in INSTRUMENT_URLS.items():
            response = self.session.get(url, timeout=60)
            if response.status_code >= 400:
                raise UpstoxError(f"Instrument master download failed for {exchange}: HTTP {response.status_code}")
            with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
                payload = json.loads(gz.read().decode("utf-8"))
            for item in payload:
                if item.get("segment") not in {"NSE_EQ", "BSE_EQ"}:
                    continue
                instrument_type = str(item.get("instrument_type", "")).upper()
                # Keep common equity series. This intentionally excludes F&O/index contracts.
                if instrument_type not in {"EQ", "BE", "BZ", "ST", "SM"}:
                    continue
                rows.append(Instrument(
                    instrument_key=item.get("instrument_key", ""),
                    exchange=item.get("exchange", exchange),
                    segment=item.get("segment", ""),
                    instrument_type=instrument_type,
                    name=item.get("name", "") or "",
                    trading_symbol=item.get("trading_symbol", "") or "",
                    short_name=item.get("short_name", "") or "",
                    isin=item.get("isin", "") or "",
                ))
        return [r for r in rows if r.instrument_key and r.trading_symbol]

    def load_instruments(self, force: bool = False) -> list[Instrument]:
        cache_file = self.cache_dir / "instruments_equity.json"
        # Reuse daily cache. Upstox describes the BOD instrument file as a daily universe.
        if not force and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < 20 * 3600:
                try:
                    raw = json.loads(cache_file.read_text(encoding="utf-8"))
                    self._instruments = [Instrument(**x) for x in raw]
                    return self._instruments
                except Exception:
                    pass
        rows = self._download_instruments()
        cache_file.write_text(
            json.dumps([r.__dict__ for r in rows], ensure_ascii=False),
            encoding="utf-8",
        )
        self._instruments = rows
        return rows

    def search_instruments(self, query: str, limit: int = 25) -> list[Instrument]:
        query = query.strip().upper()
        if not query:
            return []
        items = self.load_instruments()
        exact = []
        fuzzy = []
        for ins in items:
            fields = [
                ins.trading_symbol.upper(),
                ins.name.upper(),
                ins.short_name.upper(),
                ins.isin.upper(),
            ]
            if query == ins.trading_symbol.upper():
                exact.append(ins)
            elif any(query in field for field in fields):
                fuzzy.append(ins)
        ordered = exact + fuzzy
        # Prefer NSE if the same symbol exists on both exchanges.
        ordered.sort(key=lambda x: (0 if x.exchange == "NSE" else 1, x.trading_symbol))
        return ordered[:limit]

    def resolve_symbol(self, symbol_or_name: str) -> Instrument:
        matches = self.search_instruments(symbol_or_name, limit=50)
        if not matches:
            raise UpstoxError(f"Indian equity not found in the Upstox instrument master: {symbol_or_name}")
        return matches[0]

    # ---------- Market data ----------

    @staticmethod
    def _to_df(candles: list) -> pd.DataFrame:
        # Upstox candle arrays: timestamp, open, high, low, close, volume, oi.
        columns = ["timestamp", "open", "high", "low", "close", "volume", "oi"]
        df = pd.DataFrame(candles or [], columns=columns[:len(candles[0])] if candles else columns)
        if df.empty:
            return pd.DataFrame(columns=columns)
        for c in ["open", "high", "low", "close", "volume", "oi"]:
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata")
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        return df

    def get_intraday(self, instrument_key: str, interval: int) -> pd.DataFrame:
        url = f"{UPSTOX_API}/v3/historical-candle/intraday/{instrument_key}/minutes/{int(interval)}"
        payload = self._get_json(url)
        candles = payload.get("data", {}).get("candles", [])
        return self._to_df(candles)

    def get_historical(self, instrument_key: str, interval: int, from_date: date, to_date: date) -> pd.DataFrame:
        # V3 supports minutes 1..300. For <=15m, Upstox limits a query to one month.
        unit = "minutes"
        url = f"{UPSTOX_API}/v3/historical-candle/{instrument_key}/{unit}/{int(interval)}/{to_date.isoformat()}/{from_date.isoformat()}"
        payload = self._get_json(url)
        candles = payload.get("data", {}).get("candles", [])
        return self._to_df(candles)

    def get_recent_history(self, instrument_key: str, interval: int, calendar_days: int = 30) -> pd.DataFrame:
        to_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        from_date = to_date - timedelta(days=calendar_days)
        return self.get_historical(instrument_key, interval, from_date, to_date)

    def get_quote_batch(self, instrument_keys: Iterable[str]) -> dict:
        keys = list(instrument_keys)
        if not keys:
            return {}
        data: dict = {}
        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]
            payload = self._get_json(
                f"{UPSTOX_API}/v3/market-quote/quotes",
                params={"instrument_key": ",".join(batch)},
            )
            data.update(payload.get("data", {}))
        return data
