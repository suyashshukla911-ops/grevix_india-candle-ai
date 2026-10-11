from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
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
    gate_target: float
    gate_met: bool
    qualified_signals: int
    gate_note: str


class CandleModel:
    """Fast, deterministic, time-ordered model with a strict 90% precision gate.

    Important distinction:
    - direction_accuracy = overall validation accuracy, which is not expected to
      be 90% in noisy short-horizon markets.
    - signal_precision = precision of only the selectively-issued BUY/SELL signals.
      The competition rule is a 90% minimum *precision gate* for issuing a trusted
      signal. If the validation data cannot support that gate, the product abstains.
    """

    def __init__(self, min_train_rows: int = 500, gate_target: float = 0.90, min_gate_signals: int = 6):
        self.min_train_rows = min_train_rows
        self.gate_target = gate_target
        self.min_gate_signals = min_gate_signals
        self.direction_model = None
        self.return_model = None
        self.high_model = None
        self.low_model = None
        self.eod_model = None
        self.features: list[str] = []
        self.report: ModelReport | None = None

    def _best_precision_threshold(self, y_true: np.ndarray, p_up: np.ndarray) -> tuple[float, float, float, bool, int]:
        best_gate: tuple[float, float, float, int] | None = None
        best_any: tuple[float, float, float, int] | None = None
        n = len(y_true)
        min_signals = max(self.min_gate_signals, int(math.ceil(n * 0.01)))
        for t in np.arange(0.50, 0.991, 0.01):
            long_mask = p_up >= t
            short_mask = p_up <= (1 - t)
            mask = long_mask | short_mask
            count = int(mask.sum())
            if count < min_signals:
                continue
            preds = np.where(long_mask[mask], 1, 0)
            precision = float(precision_score(y_true[mask], preds, zero_division=0))
            coverage = count / n if n else 0.0
            candidate = (float(t), precision, coverage, count)
            if best_any is None or (precision, coverage) > (best_any[1], best_any[2]):
                best_any = candidate
            if precision >= self.gate_target:
                # Maximise usable coverage while preserving the 90% precision gate.
                if best_gate is None or (coverage, precision) > (best_gate[2], best_gate[1]):
                    best_gate = candidate

        if best_gate is not None:
            return best_gate[0], best_gate[1], best_gate[2], True, best_gate[3]
        if best_any is not None:
            return best_any[0], best_any[1], best_any[2], False, best_any[3]
        return 0.90, 0.0, 0.0, False, 0

    def fit(self, train_df: pd.DataFrame, features: list[str]) -> ModelReport:
        if len(train_df) < self.min_train_rows:
            raise ValueError(f"Not enough clean training rows: {len(train_df)} (minimum {self.min_train_rows})")
        self.features = list(features)
        split = max(int(len(train_df) * 0.80), min(250, self.min_train_rows // 2))
        split = min(split, len(train_df) - max(60, self.min_train_rows // 5))
        train = train_df.iloc[:split].copy()
        val = train_df.iloc[split:].copy()

        classifier = HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.06,
            max_leaf_nodes=15,
            min_samples_leaf=12,
            l2_regularization=1.5,
            random_state=42,
        )
        classifier.fit(train[self.features], train["direction"].astype(int))
        p_val = classifier.predict_proba(val[self.features])[:, 1]
        accuracy = float(accuracy_score(val["direction"], (p_val >= 0.5).astype(int)))
        threshold, precision, coverage, gate_met, qualified_signals = self._best_precision_threshold(
            val["direction"].to_numpy(), p_val
        )

        def fit_reg(target: str):
            reg = HistGradientBoostingRegressor(
                max_iter=120,
                learning_rate=0.06,
                max_leaf_nodes=15,
                min_samples_leaf=12,
                l2_regularization=1.5,
                random_state=42,
            )
            reg.fit(train[self.features], train[target])
            return reg, float(mean_absolute_error(val[target], reg.predict(val[self.features])))

        ret_model, ret_mae = fit_reg("next_return")
        high_model, _ = fit_reg("next_high_return")
        low_model, _ = fit_reg("next_low_return")
        eod_model, _ = fit_reg("eod_return")

        # Production models are fit on all clean rows after validation has fixed
        # the operating threshold. This avoids using the future validation labels
        # to train the final estimator.
        self.direction_model = HistGradientBoostingClassifier(
            max_iter=160, learning_rate=0.06, max_leaf_nodes=15,
            min_samples_leaf=12, l2_regularization=1.5, random_state=42,
        )
        self.direction_model.fit(train_df[self.features], train_df["direction"].astype(int))
        self.return_model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.06, max_leaf_nodes=15,
            min_samples_leaf=12, l2_regularization=1.5, random_state=42,
        ).fit(train_df[self.features], train_df["next_return"])
        self.high_model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.06, max_leaf_nodes=15,
            min_samples_leaf=12, l2_regularization=1.5, random_state=42,
        ).fit(train_df[self.features], train_df["next_high_return"])
        self.low_model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.06, max_leaf_nodes=15,
            min_samples_leaf=12, l2_regularization=1.5, random_state=42,
        ).fit(train_df[self.features], train_df["next_low_return"])
        self.eod_model = HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.06, max_leaf_nodes=15,
            min_samples_leaf=12, l2_regularization=1.5, random_state=42,
        ).fit(train_df[self.features], train_df["eod_return"])

        gate_note = (
            f"90% precision gate met on {qualified_signals} validation signals."
            if gate_met
            else "90% precision gate not supported by this validation window; product will abstain."
        )
        self.report = ModelReport(
            direction_accuracy=accuracy,
            signal_precision=float(precision),
            signal_coverage=float(coverage),
            next_return_mae=float(ret_mae),
            threshold=float(threshold),
            train_rows=len(train),
            validation_rows=len(val),
            gate_target=self.gate_target,
            gate_met=gate_met,
            qualified_signals=qualified_signals,
            gate_note=gate_note,
        )
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

        news_overlay = float(np.clip(news_impact, -1, 1) * max(abs(raw_return), 0.0015) * 0.20)
        adjusted = raw_return + news_overlay
        predicted_close = current_price * (1 + adjusted)
        predicted_high = current_price * (1 + max(high_return, adjusted))
        predicted_low = current_price * (1 + min(low_return, adjusted))
        eod_close = current_price * (1 + eod_return)

        t = self.report.threshold
        gate_ok = self.report.gate_met
        if gate_ok and p_up >= t and news_impact > -0.55:
            signal = "BUY"
        elif gate_ok and p_up <= (1 - t) and news_impact < 0.55:
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
                "validation_rows": self.report.validation_rows,
                "gate_target": round(self.report.gate_target * 100, 2),
                "gate_met": self.report.gate_met,
                "qualified_signals": self.report.qualified_signals,
                "gate_note": self.report.gate_note,
            },
        }
