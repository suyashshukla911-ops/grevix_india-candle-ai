from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

# The competition build deliberately uses a local provider. The provider boundaries
# are kept clean so live market/GitHub adapters can be added later.

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "India Candle AI")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    monitored_repo: str = os.getenv("MONITORED_REPO", "workspace/monitored_repository")
    offline_mode: bool = os.getenv("OFFLINE_MODE", "true").lower() == "true"
    max_training_rows: int = 4200
    # The minimum training requirement is interval-aware so 60m does not fail on
    # a healthy dataset simply because it has fewer rows than the 5m model.
    min_train_rows_by_interval: tuple[tuple[int, int], ...] = (
        (5, 500),
        (15, 400),
        (30, 300),
        (60, 250),
    )
    min_precision_gate: float = 0.90
    min_gate_signals: int = 6

    def min_train_rows(self, interval: int) -> int:
        for step, rows in self.min_train_rows_by_interval:
            if interval == step:
                return rows
        raise ValueError("Unsupported interval. Use 5, 15, 30 or 60 minutes.")

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

# Defaults are intentionally set to a broader timeframe that tends to have a
# higher-signal validation gate than ultra-short 5m noise.
DEFAULT_SYMBOL = "TCS"
DEFAULT_INTERVAL = 60
