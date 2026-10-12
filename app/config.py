from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

COMMON_INDIAN_STOCKS = [
    ("RELIANCE", "Reliance Industries"), ("TCS", "Tata Consultancy Services"),
    ("INFY", "Infosys"), ("HDFCBANK", "HDFC Bank"), ("ICICIBANK", "ICICI Bank"),
    ("SBIN", "State Bank of India"), ("BHARTIARTL", "Bharti Airtel"), ("ITC", "ITC"),
    ("LT", "Larsen & Toubro"), ("AXISBANK", "Axis Bank"), ("MARUTI", "Maruti Suzuki"),
    ("HINDUNILVR", "Hindustan Unilever"), ("TATAMOTORS", "Tata Motors"),
    ("TATASTEEL", "Tata Steel"), ("ADANIENT", "Adani Enterprises"), ("ADANIPORTS", "Adani Ports"),
    ("SUNPHARMA", "Sun Pharma"), ("WIPRO", "Wipro"), ("HCLTECH", "HCL Technologies"),
    ("KOTAKBANK", "Kotak Mahindra Bank"), ("BAJFINANCE", "Bajaj Finance"),
    ("M&M", "Mahindra & Mahindra"), ("ULTRACEMCO", "UltraTech Cement"), ("NTPC", "NTPC"),
    ("POWERGRID", "Power Grid"), ("ONGC", "ONGC"), ("COALINDIA", "Coal India"),
    ("TITAN", "Titan Company"), ("ASIANPAINT", "Asian Paints"), ("NESTLEIND", "Nestle India"),
    ("JSWSTEEL", "JSW Steel"), ("TECHM", "Tech Mahindra"), ("INDUSINDBK", "IndusInd Bank"),
    ("BAJAJFINSV", "Bajaj Finserv"), ("DIVISLAB", "Divi's Laboratories"),
    ("DRREDDY", "Dr Reddy's Laboratories"), ("CIPLA", "Cipla"), ("EICHERMOT", "Eicher Motors"),
    ("HEROMOTOCO", "Hero MotoCorp"), ("TVSMOTOR", "TVS Motor"), ("GRASIM", "Grasim Industries"),
    ("BRITANNIA", "Britannia"), ("APOLLOHOSP", "Apollo Hospitals"), ("BEL", "Bharat Electronics"),
    ("TRENT", "Trent"), ("JIOFIN", "Jio Financial Services"),
]

SECTOR_BY_SYMBOL = {
    "RELIANCE": "Energy / Telecom", "TCS": "IT", "INFY": "IT", "HDFCBANK": "Banking",
    "ICICIBANK": "Banking", "SBIN": "Banking", "BHARTIARTL": "Telecom", "ITC": "FMCG",
    "LT": "Infrastructure", "AXISBANK": "Banking", "MARUTI": "Automotive", "HINDUNILVR": "FMCG",
    "TATAMOTORS": "Automotive", "TATASTEEL": "Metals", "ADANIENT": "Conglomerate",
    "ADANIPORTS": "Logistics", "SUNPHARMA": "Pharma", "WIPRO": "IT", "HCLTECH": "IT",
    "KOTAKBANK": "Banking", "BAJFINANCE": "Financial Services", "M&M": "Automotive",
    "ULTRACEMCO": "Cement", "NTPC": "Power", "POWERGRID": "Power", "ONGC": "Energy",
    "COALINDIA": "Mining", "TITAN": "Consumer", "ASIANPAINT": "Consumer", "NESTLEIND": "FMCG",
    "JSWSTEEL": "Metals", "TECHM": "IT", "INDUSINDBK": "Banking", "BAJAJFINSV": "Financial Services",
    "DIVISLAB": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "EICHERMOT": "Automotive",
    "HEROMOTOCO": "Automotive", "TVSMOTOR": "Automotive", "GRASIM": "Conglomerate",
    "BRITANNIA": "FMCG", "APOLLOHOSP": "Healthcare", "BEL": "Defence", "TRENT": "Retail",
    "JIOFIN": "Financial Services",
}

INDEX_SYMBOLS = {"nifty": "^NSEI", "banknifty": "^NSEBANK", "vix": "^INDIAVIX"}

@dataclass(frozen=True)
class Settings:
    app_name: str
    default_interval: str
    train_days_intraday: int
    train_days_daily: int
    min_train_rows: int
    min_train_rows_daily: int
    min_signal_count_daily: int
    signal_precision_gate: float
    min_signal_count: int
    min_wilson_lower: float
    max_cache_hours: float
    data_timeout_seconds: float
    max_candles_display: int
    chart_candles: int
    model_refresh_minutes: int
    runtime_dir: Path
    monitored_repo: Path
    allow_fallback: bool
    replay_enabled: bool
    catalog_refresh_hours: float
    deep_security_scan: bool
    transaction_cost_bps: float
    slippage_bps: float
    min_value_traded_inr: float
    max_clone_mb: int
    max_clones: int
    auth_enabled: bool
    admin_password: str
    github_webhook_secret: str
    model_artifact_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        runtime = ROOT_DIR / os.getenv("RUNTIME_DIR", "runtime")
        monitored = ROOT_DIR  # The actual application repository is the default model-bound workspace.
        return cls(
            app_name=os.getenv("APP_NAME", "India Candle AI"),
            default_interval=os.getenv("DEFAULT_INTERVAL", "60m"),
            train_days_intraday=int(os.getenv("TRAIN_DAYS_INTRADAY", "60")),
            train_days_daily=int(os.getenv("TRAIN_DAYS_DAILY", "900")),
            min_train_rows=int(os.getenv("MIN_TRAIN_ROWS", "240")),
            min_train_rows_daily=int(os.getenv("MIN_TRAIN_ROWS_DAILY", "45")),
            min_signal_count_daily=int(os.getenv("MIN_SIGNAL_COUNT_DAILY", "15")),
            signal_precision_gate=float(os.getenv("SIGNAL_PRECISION_GATE", "0.90")),
            min_signal_count=int(os.getenv("MIN_SIGNAL_COUNT", "30")),
            min_wilson_lower=float(os.getenv("MIN_WILSON_LOWER", "0.90")),
            max_cache_hours=float(os.getenv("MAX_CACHE_HOURS", "24")),
            data_timeout_seconds=float(os.getenv("DATA_TIMEOUT_SECONDS", "10")),
            max_candles_display=int(os.getenv("MAX_CANDLES_DISPLAY", "120")),
            chart_candles=int(os.getenv("CHART_CANDLES", "48")),
            model_refresh_minutes=int(os.getenv("MODEL_REFRESH_MINUTES", "60")),
            runtime_dir=runtime,
            monitored_repo=monitored,
            allow_fallback=False,  # Synthetic fallback is intentionally disabled in the final build.
            replay_enabled=os.getenv("REPLAY_ENABLED", "true").lower() == "true",
            catalog_refresh_hours=float(os.getenv("CATALOG_REFRESH_HOURS", "12")),
            deep_security_scan=os.getenv("DEEP_SECURITY_SCAN", "true").lower() == "true",
            transaction_cost_bps=float(os.getenv("TRANSACTION_COST_BPS", "12")),
            slippage_bps=float(os.getenv("SLIPPAGE_BPS", "5")),
            min_value_traded_inr=float(os.getenv("MIN_VALUE_TRADED_INR", "5000000")),
            max_clone_mb=int(os.getenv("MAX_CLONE_MB", "150")),
            max_clones=int(os.getenv("MAX_CLONES", "3")),
            auth_enabled=os.getenv("AUTH_ENABLED", "true").lower() == "true",
            admin_password=os.getenv("ADMIN_PASSWORD", "change-me").strip(),
            github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            model_artifact_key=os.getenv("MODEL_ARTIFACT_KEY", ""),
        )

settings = Settings.from_env()
settings.runtime_dir.mkdir(parents=True, exist_ok=True)
(settings.runtime_dir / "cache").mkdir(parents=True, exist_ok=True)
(settings.runtime_dir / "models").mkdir(parents=True, exist_ok=True)
(settings.runtime_dir / "sessions").mkdir(parents=True, exist_ok=True)
AFTERCODE_ENVIRONMENT_VERSION = '20261012123515'
