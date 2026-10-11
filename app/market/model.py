from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
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
    def _select_threshold(y_true: np.ndarray, p_up: np.ndarray) -> tuple[float, float, float]:
        best = (0.65, 0.0, 0.0)
        n = len(y_true)
        for t in np.arange(0.55, 0.91, 0.01):
            long_mask = p_up >= t
            short_mask = p_up <= (1 - t)
            mask = long_mask | short_mask
            signals = int(mask.sum())
            if signals < max(10, int(n * 0.02)):
                continue
            preds = np.where(long_mask[mask], 1, 0)
            precision = precision_score(y_true[mask], preds, zero_division=0)
            coverage = signals / n if n else 0.0
            score = precision + 0.05 * math.sqrt(coverage)
            best_score = best[1] + 0.05 * math.sqrt(best[2]) if best[2] else -1
            if precision >= best[1] and score > best_score:
                best = (float(t), float(precision), float(coverage))
        return best

    def fit(self, train_df: pd.DataFrame, features: list[str]) -> ModelReport:
        if len(train_df) < self.min_train_rows:
            raise ValueError(f"Need at least {self.min_train_rows} clean rows; got {len(train_df)}")
        self.features = list(features)
        split = max(self.min_train_rows // 2, int(len(train_df) * 0.80))
        split = min(split, len(train_df) - 100)
        train = train_df.iloc[:split].copy()
        val = train_df.iloc[split:].copy()
        classifier = ExtraTreesClassifier(
            n_estimators=180, max_depth=12, min_samples_leaf=3,
            n_jobs=-1, random_state=42, class_weight="balanced_subsample"
        )
        classifier.fit(train[self.features], train["direction"].astype(int))
        p_val = classifier.predict_proba(val[self.features])[:, 1]
        threshold, precision, coverage = self._select_threshold(val["direction"].to_numpy(), p_val)
        accuracy = accuracy_score(val["direction"], (p_val >= 0.5).astype(int))

        def fit_reg(target: str) -> tuple[object, float]:
            reg = ExtraTreesRegressor(
                n_estimators=180, max_depth=12, min_samples_leaf=3,
                n_jobs=-1, random_state=42
            )
            reg.fit(train[self.features], train[target])
            return reg, float(mean_absolute_error(val[target], reg.predict(val[self.features])))

        ret_model, ret_mae = fit_reg("next_return")
        high_model, _ = fit_reg("next_high_return")
        low_model, _ = fit_reg("next_low_return")
        eod_model, _ = fit_reg("eod_return")
        self.direction_model = clone(classifier)
        self.direction_model.fit(train_df[self.features], train_df["direction"].astype(int))
        self.return_model = clone(ret_model); self.return_model.fit(train_df[self.features], train_df["next_return"])
        self.high_model = clone(high_model); self.high_model.fit(train_df[self.features], train_df["next_high_return"])
        self.low_model = clone(low_model); self.low_model.fit(train_df[self.features], train_df["next_low_return"])
        self.eod_model = clone(eod_model); self.eod_model.fit(train_df[self.features], train_df["eod_return"])
        self.report = ModelReport(float(accuracy), float(precision), float(coverage), float(ret_mae), float(threshold), len(train), len(val))
        return self.report

    def predict(self, latest_row: pd.DataFrame, current_price: float, news_impact: float = 0.0) -> dict:
        if self.report is None or self.direction_model is None:
            raise RuntimeError("Model is not trained")
        X = latest_row[self.features]
        p_up = float(self.direction_model.predict_proba(X)[0, 1])
        raw_return = float(self.return_model.predict(X)[0])
        high_return = float(self.high_model.predict(X)[0])
        low_return = float(self.low_model.predict(X)[0])
        eod_return = float(self.eod_model.predict(X)[0])
        news_overlay = float(np.clip(news_impact, -1, 1) * max(abs(raw_return), 0.0015) * 0.30)
        adjusted = raw_return + news_overlay
        predicted_close = current_price * (1 + adjusted)
        predicted_high = current_price * (1 + max(high_return, adjusted))
        predicted_low = current_price * (1 + min(low_return, adjusted))
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
            "predicted_close": round(predicted_close, 4),
            "predicted_high": round(max(predicted_high, predicted_close), 4),
            "predicted_low": round(min(predicted_low, predicted_close), 4),
            "predicted_eod_close": round(eod_close, 4),
            "raw_return": round(raw_return, 6),
            "news_adjusted_return": round(adjusted, 6),
            "eod_return": round(eod_return, 6),
            "validation": {
                "direction_accuracy": round(self.report.direction_accuracy * 100, 2),
                "signal_precision": round(self.report.signal_precision * 100, 2),
                "signal_coverage": round(self.report.signal_coverage * 100, 2),
                "next_return_mae": round(self.report.next_return_mae, 6),
                "threshold": round(self.report.threshold, 2),
                "train_rows": self.report.train_rows,
                "validation_rows": self.report.validation_rows,
            },
        }
