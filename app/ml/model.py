from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from importlib.metadata import version as pkg_version

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from scipy.stats import norm

from app.config import settings

@dataclass(frozen=True)
class ThresholdSelection:
    threshold: float
    calibration_precision: float
    calibration_coverage: float
    calibration_signals: int
    gate_candidate: bool

    def __iter__(self):
        # Backwards-compatible unpacking for earlier tests/clients.
        yield self.threshold
        yield self.calibration_precision
        yield self.calibration_coverage
        yield self.gate_candidate

@dataclass
class ModelReport:
    direction_accuracy: float
    signal_precision: float
    signal_coverage: float
    precision_lower_bound: float
    signal_count: int
    next_return_mae: float
    next_return_r2: float
    threshold: float
    gate_pass: bool
    train_rows: int
    calibration_rows: int
    validation_rows: int
    classifier_name: str
    dataset_fingerprint: str = ""
    model_version: str = ""
    trained_at: str = ""
    training_seconds: float = 0.0
    environment_fingerprint: str = ""
    calibration_brier: float = 0.0
    package_versions: dict[str, str] | None = None

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("direction_accuracy","signal_precision","signal_coverage","precision_lower_bound"):
            d[k] = round(d[k] * 100, 2)
        d["next_return_mae"] = round(d["next_return_mae"], 6)
        d["next_return_r2"] = round(d["next_return_r2"], 4)
        d["threshold"] = round(d["threshold"], 3)
        d["calibration_brier"] = round(d["calibration_brier"], 5)
        return d

def wilson_lower(successes: int, total: int, confidence: float = 0.95) -> float:
    if total <= 0:
        return 0.0
    z = float(norm.ppf(0.5 + confidence / 2))
    phat = successes / total
    denom = 1 + z*z/total
    center = phat + z*z/(2*total)
    margin = z * math.sqrt((phat*(1-phat) + z*z/(4*total))/total)
    return max(0.0, (center-margin)/denom)

class CandleModel:
    def __init__(self, min_train_rows: int | None = None):
        self.min_train_rows = min_train_rows or settings.min_train_rows
        self.features: list[str] = []
        self.classifier = None
        self.calibrator: IsotonicRegression | None = None
        self.regressors: dict[str, Any] = {}
        self.report: ModelReport | None = None
        self.validation_predictions: pd.DataFrame | None = None

    @staticmethod
    def _candidate_classifier():
        return HistGradientBoostingClassifier(
            max_depth=5, learning_rate=0.055, max_iter=180,
            l2_regularization=0.7, random_state=42
        )

    @staticmethod
    def _candidate_regressor():
        return HistGradientBoostingRegressor(
            max_depth=5, learning_rate=0.055, max_iter=160,
            l2_regularization=0.7, loss="absolute_error", random_state=42
        )

    @staticmethod
    def _probabilities(model, calibrator, X):
        raw = model.predict_proba(X)[:, 1]
        if calibrator is None:
            return raw
        return np.clip(calibrator.predict(raw), 0.0, 1.0)

    @staticmethod
    def optimize_threshold(
        y_true: np.ndarray,
        p_up: np.ndarray,
        minimum_precision: float = 0.90,
        actual_returns: np.ndarray | None = None,
        min_signals: int = settings.min_signal_count,
    ) -> ThresholdSelection:
        n = len(y_true)
        if n == 0:
            return ThresholdSelection(0.90, 0.0, 0.0, 0, False)
        min_signals = max(int(min_signals), 1)
        candidates: list[ThresholdSelection] = []
        for t in np.arange(0.55, 0.951, 0.01):
            long = p_up >= t
            short = p_up <= (1 - t)
            mask = long | short
            count = int(mask.sum())
            if count < min_signals:
                continue
            if actual_returns is None:
                pred = np.where(long[mask], 1, 0)
                wins = (pred == y_true[mask]).sum()
            else:
                r = np.asarray(actual_returns)[mask]
                wins = int(((long[mask] & (r > 0)) | (short[mask] & (r < 0))).sum())
            precision = wins / count if count else 0.0
            coverage = count / n
            candidates.append(
                ThresholdSelection(float(t), float(precision), float(coverage), count, precision >= minimum_precision)
            )
        passing = [x for x in candidates if x.gate_candidate]
        if passing:
            passing.sort(key=lambda x: (x.calibration_coverage, x.calibration_precision), reverse=True)
            return passing[0]
        if candidates:
            candidates.sort(key=lambda x: (x.calibration_precision, x.calibration_coverage), reverse=True)
            return candidates[0]
        return ThresholdSelection(0.90, 0.0, 0.0, 0, False)

    def fit(self, train_df: pd.DataFrame, features: list[str], dataset_fingerprint: str = "", environment_fingerprint: str = "", min_signal_count: int | None = None, min_validation_rows: int = 30, min_calibration_rows: int = 30) -> ModelReport:
        if len(train_df) < self.min_train_rows:
            raise ValueError(f"Need at least {self.min_train_rows} clean rows; got {len(train_df)}.")
        start = datetime.now().timestamp()
        self.features = list(features)
        # Strict temporal split: fit -> calibration -> untouched holdout.
        n = len(train_df)
        min_test = min(min_validation_rows, max(15, n // 5))
        min_cal = min(min_calibration_rows, max(15, n // 5))
        test_len = max(min_test, int(n * 0.20))
        cal_len = max(min_cal, int(n * 0.20))
        if n - test_len - cal_len < max(30, int(n * 0.35)):
            test_len = max(min_test, int(n * 0.18))
            cal_len = max(min_cal, int(n * 0.18))
        train_len = n - cal_len - test_len
        if train_len < 30 or cal_len < 15 or test_len < 15:
            raise ValueError("Not enough rows for chronological fit/calibration/holdout validation.")
        fit = train_df.iloc[:train_len].copy()
        calibration = train_df.iloc[train_len:train_len + cal_len].copy()
        test = train_df.iloc[train_len + cal_len:].copy()

        y_fit = fit.direction.astype(int)
        y_cal = calibration.direction.astype(int)
        y_test = test.direction.astype(int)

        self.classifier = self._candidate_classifier()
        self.classifier.fit(fit[self.features], y_fit)
        p_cal_raw = self.classifier.predict_proba(calibration[self.features])[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.calibrator.fit(p_cal_raw, y_cal.to_numpy())
        p_cal = self._probabilities(self.classifier, self.calibrator, calibration[self.features])
        threshold_sel = self.optimize_threshold(
            y_cal.to_numpy(), p_cal, settings.signal_precision_gate,
            actual_returns=calibration.execution_return.to_numpy(),
            min_signals=min_signal_count or settings.min_signal_count,
        )
        p_test = self._probabilities(self.classifier, self.calibrator, test[self.features])
        t = threshold_sel.threshold
        long = p_test >= t
        short = p_test <= 1 - t
        sig_mask = long | short
        signal_count = int(sig_mask.sum())
        wins = int((((long[sig_mask]) & (test.execution_return.to_numpy()[sig_mask] > 0)) |
                    ((short[sig_mask]) & (test.execution_return.to_numpy()[sig_mask] < 0))).sum()) if signal_count else 0
        precision = wins / signal_count if signal_count else 0.0
        lower = wilson_lower(wins, signal_count) if signal_count else 0.0
        coverage = signal_count / max(1, len(test))
        direction_accuracy = float(accuracy_score(y_test, (p_test >= 0.5).astype(int)))

        # Regressions are fit on fit+calibration and evaluated on untouched test.
        train_for_reg = pd.concat([fit, calibration], ignore_index=True)
        reg_metrics = []
        self.regressors = {}
        for target in ["next_return","next_high_return","next_low_return","eod_return"]:
            reg = self._candidate_regressor()
            reg.fit(train_for_reg[self.features], train_for_reg[target])
            pred = reg.predict(test[self.features])
            reg_metrics.append((target, mean_absolute_error(test[target], pred), r2_score(test[target], pred)))
            self.regressors[target] = reg

        # The shipped classifier is the calibrated fit model; metrics above refer to it.
        rr = next(x for x in reg_metrics if x[0] == "next_return")
        brier = float(np.mean((p_test - y_test.to_numpy())**2))
        package_versions = {}
        for package in ("numpy", "pandas", "scikit-learn", "scipy", "yfinance"):
            try:
                package_versions[package] = pkg_version(package)
            except Exception:
                package_versions[package] = "unknown"
        gate = (
            signal_count >= (min_signal_count or settings.min_signal_count)
            and precision >= settings.signal_precision_gate
            and lower >= settings.min_wilson_lower
        )
        meta = json.dumps({
            "features": self.features, "threshold": t, "classifier": "histgb",
            "dataset": dataset_fingerprint, "environment": environment_fingerprint,
            "gate": settings.signal_precision_gate, "min_signals": settings.min_signal_count,
            "wilson_lower": lower,
        }, sort_keys=True)
        version = "v" + hashlib.sha256(meta.encode()).hexdigest()[:10]
        self.validation_predictions = pd.DataFrame({
            "timestamp": test["timestamp"].to_numpy(),
            "open": test["open"].to_numpy(),
            "close": test["close"].to_numpy(),
            "actual_return": test["next_return"].to_numpy(),
            "execution_return": test["execution_return"].to_numpy(),
            "return_1": test["return_1"].to_numpy() if "return_1" in test.columns else np.zeros(len(test)),
            "p_up": p_test,
        })
        self.report = ModelReport(
            direction_accuracy=direction_accuracy,
            signal_precision=precision,
            signal_coverage=coverage,
            precision_lower_bound=lower,
            signal_count=signal_count,
            next_return_mae=float(rr[1]),
            next_return_r2=float(rr[2]),
            threshold=float(t),
            gate_pass=bool(gate),
            train_rows=len(fit),
            calibration_rows=len(calibration),
            validation_rows=len(test),
            classifier_name="histgb-calibrated",
            dataset_fingerprint=dataset_fingerprint,
            model_version=version,
            trained_at=datetime.now().astimezone().isoformat(),
            training_seconds=round(datetime.now().timestamp() - start, 3),
            environment_fingerprint=environment_fingerprint,
            calibration_brier=brier,
            package_versions=package_versions,
        )
        return self.report

    def backtest(self) -> dict[str, Any]:
        if self.report is None or self.validation_predictions is None:
            raise RuntimeError("Fit the model before backtesting.")
        d = self.validation_predictions.copy().sort_values("timestamp").reset_index(drop=True)
        t = self.report.threshold
        d["signal"] = "HOLD"
        d.loc[d.p_up >= t, "signal"] = "BUY"
        d.loc[d.p_up <= 1 - t, "signal"] = "SELL / EXIT"
        cost = (settings.transaction_cost_bps + settings.slippage_bps) / 10000.0
        d["paper_return"] = np.where(
            d.signal.eq("BUY"), d.execution_return - cost,
            np.where(d.signal.eq("SELL / EXIT"), -d.execution_return - cost, 0.0)
        )
        d["equity"] = (1 + d.paper_return.fillna(0)).cumprod()
        buyhold = 0.0
        if len(d) >= 2 and float(d.close.iloc[0]) != 0:
            buyhold = float(d.close.iloc[-1] / d.close.iloc[0] - 1)
        peak = d.equity.cummax()
        drawdown = d.equity / peak - 1
        wins = d.loc[d.paper_return > 0, "paper_return"]
        losses = d.loc[d.paper_return < 0, "paper_return"]
        signals = d[d.signal != "HOLD"]
        naive = np.sign(d["return_1"].fillna(0).to_numpy()) if "return_1" in d.columns else np.zeros(len(d))
        actual_dir = np.sign(d["actual_return"].fillna(0).to_numpy())
        naive_mask = naive != 0
        naive_accuracy = float((naive[naive_mask] == actual_dir[naive_mask]).mean() * 100) if naive_mask.any() else 0.0
        return {
            "validation_period": f"{d.timestamp.iloc[0].isoformat()} -> {d.timestamp.iloc[-1].isoformat()}",
            "signals": int(len(signals)),
            "wins": int((signals.paper_return > 0).sum()),
            "losses": int((signals.paper_return < 0).sum()),
            "signal_precision": round(float((signals.paper_return > 0).mean() * 100) if len(signals) else 0.0, 2),
            "strategy_return_pct": round(float((d.equity.iloc[-1] - 1) * 100), 2),
            "buy_hold_return_pct": round(buyhold * 100, 2),
            "max_drawdown_pct": round(float(drawdown.min() * 100), 2),
            "profit_factor": round(float(wins.sum() / abs(losses.sum())), 2) if losses.sum() < 0 else None,
            "coverage_pct": round(float(len(signals) / len(d) * 100), 2),
            "naive_direction_accuracy_pct": round(naive_accuracy, 2),
            "entry_model": "Next bar/session OPEN entry; next CLOSE exit",
            "cost_assumption_bps_roundtrip": settings.transaction_cost_bps + settings.slippage_bps,
            "position_sizing": "1x notional per qualifying signal; no leverage",
            "stop_target": "Volatility heuristic only; not backtest-validated",
        }

    def predict(self, latest: pd.DataFrame, current_price: float, news_impact: float, regime: dict[str, str],
                repo_current: bool, data_current: bool, market_open: bool = True,
                liquidity_ok: bool = True) -> dict[str, Any]:
        if not self.report or self.classifier is None:
            raise RuntimeError("Model is not trained.")
        X = latest[self.features]
        p_up = float(self._probabilities(self.classifier, self.calibrator, X)[0])
        outputs = {key: float(model.predict(X)[0]) for key, model in self.regressors.items()}
        t = self.report.threshold
        if not liquidity_ok:
            signal = "HOLD"
        elif not repo_current or not data_current:
            signal = "REVALIDATE"
        elif not self.report.gate_pass:
            signal = "NO-TRADE"
        elif p_up >= t:
            signal = "BUY"
        elif p_up <= 1 - t:
            signal = "SELL / EXIT"
        else:
            signal = "HOLD"

        confidence = round(max(p_up, 1 - p_up) * 100, 2)
        return {
            "signal": signal,
            "trading_action": signal,
            "probability_up": round(p_up, 4),
            "probability_down": round(1-p_up, 4),
            "confidence": confidence,
            "predicted_close": round(current_price * (1 + outputs["next_return"]), 4),
            "predicted_high": round(current_price * (1 + max(outputs["next_high_return"], outputs["next_return"])), 4),
            "predicted_low": round(current_price * (1 + min(outputs["next_low_return"], outputs["next_return"])), 4),
            "predicted_eod_close": round(current_price * (1 + outputs["eod_return"]), 4),
            "expected_return_pct": round(outputs["next_return"] * 100, 3),
            "validation": self.report.public(),
            "backtest": self.backtest(),
            "probability_note": "Calibrated holdout probability; not a guarantee of future return.",
            "paper_only": True,
        }
# AFTERCODE_SIMULATION: prediction environment updated 20261012115837
# AFTERCODE_SIMULATION: prediction environment updated 20261012123515
