
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, precision_score


@dataclass
class ModelReport:
    direction_accuracy: float
    signal_precision: float
    signal_coverage: float
    next_return_mae: float
    threshold: float
    train_rows: int
    validation_rows: int


class CandleModel:
    def __init__(self, min_train_rows: int = 500):
        self.min_train_rows = min_train_rows
        self.direction_model = None
        self.return_model = None
        self.high_model = None
        self.low_model = None
        self.eod_model = None
        self.features: list[str] = []
        self.report: ModelReport | None = None

    @staticmethod
    def _models():
        return [
            ("hgb", HistGradientBoostingClassifier(max_depth=6, learning_rate=0.05, max_iter=350, random_state=42)),
            ("rf", RandomForestClassifier(n_estimators=220, max_depth=10, min_samples_leaf=4, n_jobs=-1, random_state=42, class_weight="balanced_subsample")),
            ("et", ExtraTreesClassifier(n_estimators=220, max_depth=12, min_samples_leaf=3, n_jobs=-1, random_state=42, class_weight="balanced_subsample")),
        ]

    @staticmethod
    def _reg_models():
        return [
            ("hgb", HistGradientBoostingRegressor(max_depth=6, learning_rate=0.05, max_iter=350, loss="absolute_error", random_state=42)),
            ("rf", RandomForestRegressor(n_estimators=220, max_depth=10, min_samples_leaf=4, n_jobs=-1, random_state=42)),
            ("et", ExtraTreesRegressor(n_estimators=220, max_depth=12, min_samples_leaf=3, n_jobs=-1, random_state=42)),
        ]

    @staticmethod
    def _select_threshold(y_true: np.ndarray, p_up: np.ndarray) -> tuple[float, float, float]:
        best = (0.65, 0.0, 0.0)
        n = len(y_true)
        for t in np.arange(0.55, 0.91, 0.01):
            long_mask = p_up >= t
            short_mask = p_up <= (1 - t)
            mask = long_mask | short_mask
            signals = int(mask.sum())
            if signals < max(10, int(n * 0.01)):
                continue
            preds = np.where(long_mask[mask], 1, 0)
            true = y_true[mask]
            precision = precision_score(true, preds, zero_division=0)
            coverage = signals / n if n else 0.0
            # Favor precision first, but do not choose a threshold with almost no coverage.
            score = precision + 0.05 * math.sqrt(coverage)
            best_score = best[1] + 0.05 * math.sqrt(best[2]) if best[2] else -1
            if precision >= best[1] and score > best_score:
                best = (float(t), float(precision), float(coverage))
        return best

    @staticmethod
    def _fit_best_classifier(X_train, y_train, X_val, y_val):
        best_name = None
        best_model = None
        best_score = (-1.0, -1.0)
        for name, model in CandleModel._models():
            model.fit(X_train, y_train)
            p = model.predict_proba(X_val)[:, 1]
            acc = accuracy_score(y_val, (p >= 0.5).astype(int))
            # Use Brier-like closeness in addition to raw accuracy.
            brier = np.mean((p - y_val.to_numpy()) ** 2)
            score = (float(acc), -float(brier))
            if score > best_score:
                best_score = score
                best_name, best_model = name, model
        return best_name, best_model

    @staticmethod
    def _fit_best_regressor(X_train, y_train, X_val, y_val):
        best_name = None
        best_model = None
        best_mae = float("inf")
        for name, model in CandleModel._reg_models():
            model.fit(X_train, y_train)
            pred = model.predict(X_val)
            mae = mean_absolute_error(y_val, pred)
            if mae < best_mae:
                best_mae = mae
                best_name, best_model = name, model
        return best_name, best_model, float(best_mae)

    def fit(self, train_df: pd.DataFrame, features: list[str]) -> ModelReport:
        if len(train_df) < self.min_train_rows:
            raise ValueError(f"Need at least {self.min_train_rows} clean intraday rows; got {len(train_df)}.")

        self.features = list(features)
        split = int(len(train_df) * 0.80)
        split = max(self.min_train_rows // 2, min(split, len(train_df) - 100))
        train = train_df.iloc[:split].copy()
        val = train_df.iloc[split:].copy()

        X_train = train[self.features]
        X_val = val[self.features]
        y_train = train["direction"].astype(int)
        y_val = val["direction"].astype(int)

        _, dir_model = self._fit_best_classifier(X_train, y_train, X_val, y_val)
        p_val = dir_model.predict_proba(X_val)[:, 1]
        threshold, signal_precision, signal_coverage = self._select_threshold(y_val.to_numpy(), p_val)
        acc = accuracy_score(y_val, (p_val >= 0.5).astype(int))

        _, ret_model, ret_mae = self._fit_best_regressor(X_train, train["next_return"], X_val, val["next_return"])
        _, hi_model, _ = self._fit_best_regressor(X_train, train["next_high_return"], X_val, val["next_high_return"])
        _, lo_model, _ = self._fit_best_regressor(X_train, train["next_low_return"], X_val, val["next_low_return"])
        _, eod_model, _ = self._fit_best_regressor(X_train, train["eod_return"], X_val, val["eod_return"])

        # Refit each selected estimator on all available history for live inference.
        self.direction_model = clone(dir_model)
        self.return_model = clone(ret_model)
        self.high_model = clone(hi_model)
        self.low_model = clone(lo_model)
        self.eod_model = clone(eod_model)

        self.direction_model.fit(train_df[self.features], train_df["direction"].astype(int))
        self.return_model.fit(train_df[self.features], train_df["next_return"])
        self.high_model.fit(train_df[self.features], train_df["next_high_return"])
        self.low_model.fit(train_df[self.features], train_df["next_low_return"])
        self.eod_model.fit(train_df[self.features], train_df["eod_return"])

        self.report = ModelReport(
            direction_accuracy=float(acc),
            signal_precision=float(signal_precision),
            signal_coverage=float(signal_coverage),
            next_return_mae=float(ret_mae),
            threshold=float(threshold),
            train_rows=len(train),
            validation_rows=len(val),
        )
        return self.report

    def predict(self, latest_row: pd.DataFrame, current_price: float, news_impact: float = 0.0) -> dict:
        if self.report is None or self.direction_model is None:
            raise RuntimeError("Model is not trained.")
        X = latest_row[self.features]
        p_up = float(self.direction_model.predict_proba(X)[0, 1])
        raw_return = float(self.return_model.predict(X)[0])
        high_return = float(self.high_model.predict(X)[0])
        low_return = float(self.low_model.predict(X)[0])
        eod_return = float(self.eod_model.predict(X)[0])

        # News is intentionally a capped overlay, not a fake exact-price model.
        # It can move the scenario, but never overpower the market model.
        news_overlay = float(np.clip(news_impact, -1, 1) * max(abs(raw_return), 0.0015) * 0.35)
        news_adjusted_return = raw_return + news_overlay

        predicted_close = current_price * (1 + raw_return)
        predicted_high = current_price * (1 + max(high_return, raw_return))
        predicted_low = current_price * (1 + min(low_return, raw_return))
        eod_close = current_price * (1 + eod_return)

        t = self.report.threshold
        if p_up >= t and news_impact > -0.55:
            signal = "BUY"
        elif p_up <= (1 - t) and news_impact < 0.55:
            signal = "SELL"
        else:
            signal = "NO-TRADE"

        return {
            "signal": signal,
            "probability_up": round(p_up, 4),
            "probability_down": round(1 - p_up, 4),
            "raw_return": round(raw_return, 6),
            "news_adjusted_return": round(news_adjusted_return, 6),
            "predicted_close": round(predicted_close, 4),
            "predicted_high": round(max(predicted_high, predicted_close), 4),
            "predicted_low": round(min(predicted_low, predicted_close), 4),
            "eod_return": round(eod_return, 6),
            "predicted_eod_close": round(eod_close, 4),
            "validation": {
                "direction_accuracy": round(self.report.direction_accuracy * 100, 2),
                "signal_precision": round(self.report.signal_precision * 100, 2),
                "signal_coverage": round(self.report.signal_coverage * 100, 2),
                "next_return_mae": round(self.report.next_return_mae, 6),
                "threshold": round(self.report.threshold, 2),
                "train_rows": int(self.report.train_rows),
                "validation_rows": int(self.report.validation_rows),
            },
        }
