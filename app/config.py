from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "India Candle AI")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    monitored_repo: str = os.getenv("MONITORED_REPO", "workspace/monitored_repository")
    offline_mode: bool = os.getenv("OFFLINE_MODE", "true").lower() == "true"
    max_training_rows: int = 4200
    min_train_rows: int = 500

settings = Settings()

PRIORITY_STOCKS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries", "sector": "Energy / Consumer"},
    {"symbol": "TCS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "INFY", "name": "Infosys", "sector": "IT"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors", "sector": "Automotive"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel", "sector": "Telecom"},
]
