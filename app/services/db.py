from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings

DB_PATH = settings.runtime_dir / "trustgraph.sqlite3"

def connect():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS signal_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            candle_ts TEXT,
            signal TEXT NOT NULL,
            confidence REAL,
            probability_up REAL,
            precision REAL,
            model_version TEXT,
            repo_state TEXT,
            data_state TEXT,
            current_price REAL,
            predicted_close REAL,
            actual_close REAL,
            outcome TEXT,
            pnl_pct REAL,
            settled_at TEXT,
            journal_key TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS model_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            symbol TEXT NOT NULL,
            interval TEXT NOT NULL,
            model_version TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        """)
        # Lightweight migrations for older local DBs.
        cols = {r["name"] for r in con.execute("PRAGMA table_info(signal_journal)").fetchall()}
        for col, ddl in {
            "candle_ts": "ALTER TABLE signal_journal ADD COLUMN candle_ts TEXT",
            "actual_close": "ALTER TABLE signal_journal ADD COLUMN actual_close REAL",
            "outcome": "ALTER TABLE signal_journal ADD COLUMN outcome TEXT",
            "pnl_pct": "ALTER TABLE signal_journal ADD COLUMN pnl_pct REAL",
            "settled_at": "ALTER TABLE signal_journal ADD COLUMN settled_at TEXT",
            "journal_key": "ALTER TABLE signal_journal ADD COLUMN journal_key TEXT",
        }.items():
            if col not in cols:
                try:
                    con.execute(ddl)
                except sqlite3.OperationalError:
                    pass
        con.commit()

def audit(event: str, status: str, payload: Any):
    with connect() as con:
        con.execute(
            "INSERT INTO audit_events(ts,event,status,payload) VALUES(?,?,?,?)",
            (datetime.now().astimezone().isoformat(), event, status, json.dumps(payload, default=str))
        )
        con.commit()

def settle_previous_signal(symbol: str, interval: str, candle_ts: str, actual_close: float):
    with connect() as con:
        rows = con.execute("""
            SELECT * FROM signal_journal
            WHERE symbol=? AND interval=? AND actual_close IS NULL
            ORDER BY id DESC LIMIT 20
        """, (symbol, interval)).fetchall()
        now = datetime.now().astimezone().isoformat()
        for row in rows:
            sig_ts = row["candle_ts"] or row["ts"]
            if sig_ts >= candle_ts:
                continue
            signal = row["signal"]
            prev = row["current_price"]
            if prev is None or actual_close is None:
                continue
            move = (actual_close / prev - 1) * 100
            if signal == "BUY":
                outcome = "WIN" if move > 0 else "LOSS"
                pnl = move
            elif signal in {"SELL", "SELL / EXIT"}:
                outcome = "WIN" if move < 0 else "LOSS"
                pnl = -move
            else:
                outcome = "NOT_EVALUATED"
                pnl = 0.0
            con.execute("""
                UPDATE signal_journal
                SET actual_close=?, outcome=?, pnl_pct=?, settled_at=?
                WHERE id=?
            """, (actual_close, outcome, pnl, now, row["id"]))
        con.commit()

def journal_signal(payload: dict[str, Any]):
    candle_ts = str(payload.get("candle_ts") or "")
    symbol = payload["symbol"]
    interval = payload["interval"]
    settle_price = payload.get("settle_price")
    if settle_price is not None:
        settle_previous_signal(symbol, interval, candle_ts, float(settle_price))
    key = f"{symbol}|{interval}|{candle_ts}|{payload.get('model_version','')}"
    with connect() as con:
        con.execute("""
        INSERT OR IGNORE INTO signal_journal(
            ts,symbol,interval,candle_ts,signal,confidence,probability_up,precision,
            model_version,repo_state,data_state,current_price,predicted_close,journal_key
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().astimezone().isoformat(), symbol, interval, candle_ts,
            payload["signal"], payload.get("confidence"), payload.get("probability_up"),
            payload.get("precision"), payload.get("model_version"), payload.get("repo_state"),
            payload.get("data_state"), payload.get("current_price"), payload.get("predicted_close"),
            key
        ))
        con.commit()

def save_model_run(symbol: str, interval: str, model_version: str, payload: dict[str, Any]):
    with connect() as con:
        con.execute(
            "INSERT INTO model_runs(ts,symbol,interval,model_version,payload) VALUES(?,?,?,?,?)",
            (datetime.now().astimezone().isoformat(), symbol, interval, model_version, json.dumps(payload, default=str))
        )
        con.commit()

def recent(table: str, limit: int = 20):
    allowed = {"audit_events", "signal_journal", "model_runs"}
    if table not in allowed:
        raise ValueError("invalid table")
    with connect() as con:
        rows = con.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

init_db()
