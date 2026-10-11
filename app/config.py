
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


PRIORITY_STOCKS = [
    {"name": "United Spirits", "symbol": "UNITEDSPIR", "aliases": ["UNITED SPIRITS", "MCOWELL", "MCDOWELL-N"]},
    {"name": "Sula Vineyards", "symbol": "SULA", "aliases": ["SULA VINEYARDS"]},
    {"name": "Globus Spirits", "symbol": "GLOBUSSPR", "aliases": ["GLOBUS SPIRITS"]},
    {"name": "Radico Khaitan", "symbol": "RADICO", "aliases": ["RADICO KHAITAN"]},
    {"name": "Cupid", "symbol": "CUPID", "aliases": ["CUPID LIMITED"]},
    {"name": "Meesho", "symbol": "MEESHO", "aliases": ["MEESHO LIMITED"]},
    {"name": "Raymond", "symbol": "RAYMOND", "aliases": ["RAYMOND LIMITED"]},
    {"name": "Kalyan Jewellers", "symbol": "KALYANKJIL", "aliases": ["KALYAN JEWELLERS", "KALYAN JEWELLERS INDIA"]},
    {"name": "Orient Electric", "symbol": "ORIENTELEC", "aliases": ["ORIENT ELECTRIC"]},
    {"name": "MRF", "symbol": "MRF", "aliases": ["MRF LIMITED"]},
    {"name": "Tata Motors", "symbol": "TATAMOTORS", "aliases": ["TATA MOTORS", "TATA MOTORS LIMITED"]},
    {"name": "HDFC Bank", "symbol": "HDFCBANK", "aliases": ["HDFC BANK", "HDFC BANK LIMITED"]},
]

SECTOR_BY_SYMBOL = {
    "UNITEDSPIR": "Alcohol & Beverages",
    "SULA": "Alcohol & Beverages",
    "GLOBUSSPR": "Alcohol & Beverages",
    "RADICO": "Alcohol & Beverages",
    "CUPID": "Consumer / Healthcare",
    "MEESHO": "Internet / Consumer",
    "RAYMOND": "Textiles / Consumer",
    "KALYANKJIL": "Jewellery / Consumer",
    "ORIENTELEC": "Consumer Durables",
    "MRF": "Automotive / Tyres",
    "TATAMOTORS": "Automotive",
    "HDFCBANK": "Banking",
}

@dataclass(frozen=True)
class Settings:
    app_name: str
    base_url: str
    upstox_client_id: str
    upstox_client_secret: str
    upstox_redirect_uri: str
    upstox_access_token: str
    news_provider: str
    news_max_records: int
    default_interval: int
    train_calendar_days: int
    min_train_rows: int
    watch_refresh_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "India Candle AI"),
            base_url=os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/"),
            upstox_client_id=os.getenv("UPSTOX_CLIENT_ID", ""),
            upstox_client_secret=os.getenv("UPSTOX_CLIENT_SECRET", ""),
            upstox_redirect_uri=os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/auth/upstox/callback"),
            upstox_access_token=os.getenv("UPSTOX_ACCESS_TOKEN", ""),
            news_provider=os.getenv("NEWS_PROVIDER", "gdelt"),
            news_max_records=int(os.getenv("NEWS_MAX_RECORDS", "50")),
            default_interval=int(os.getenv("DEFAULT_INTERVAL", "5")),
            train_calendar_days=int(os.getenv("TRAIN_CALENDAR_DAYS", "30")),
            min_train_rows=int(os.getenv("MIN_TRAIN_ROWS", "500")),
            watch_refresh_seconds=int(os.getenv("WATCH_REFRESH_SECONDS", "60")),
        )

settings = Settings.from_env()
