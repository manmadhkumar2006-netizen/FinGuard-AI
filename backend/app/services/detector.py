from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


@dataclass
class DetectionResult:
    anomaly_score: float
    risk_score: int
    factors: list[str]


class AnomalyDetector:
    """Isolation Forest wrapper. Input rows are synthetic, never banking records."""

    def __init__(self) -> None:
        self.scaler = RobustScaler()
        self.model = IsolationForest(n_estimators=160, contamination=0.13, random_state=42)

    @staticmethod
    def features(rows: list[dict]) -> np.ndarray:
        return np.array([
            [
                np.log1p(r["amount"]), r["account_age_days"], r["velocity_24h"],
                int(r["is_international"]), r["hour"], r["merchant_risk"],
            ] for r in rows
        ])

    def score(self, rows: list[dict]) -> list[DetectionResult]:
        matrix = self.scaler.fit_transform(self.features(rows))
        self.model.fit(matrix)
        raw = -self.model.score_samples(matrix)
        low, high = float(raw.min()), float(raw.max())
        normalized = (raw - low) / (high - low + 1e-9)
        results = []
        for row, signal in zip(rows, normalized):
            factors = []
            if row["amount"] > 2500: factors.append("Unusual transaction amount")
            if row["velocity_24h"] >= 6: factors.append("High transaction velocity")
            if row["is_international"]: factors.append("International payment pattern")
            if row["account_age_days"] < 21: factors.append("New account activity")
            if row["merchant_risk"] > .70: factors.append("Elevated merchant risk")
            if row["hour"] < 5: factors.append("Unusual transaction time")
            score = int(np.clip(16 + signal * 64 + min(len(factors) * 4, 20), 0, 100))
            if score >= 65 and not factors: factors.append("Behavioral anomaly detected")
            results.append(DetectionResult(round(float(signal), 3), score, factors or ["Normal behavioral pattern"]))
        return results
