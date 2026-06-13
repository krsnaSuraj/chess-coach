"""XGBoost ML risk classifier for anti-detection."""
from __future__ import annotations
import numpy as np
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RiskAssessment:
    score: int
    level: str
    signals_above_threshold: int
    recommendation: str

class RiskClassifier:
    def __init__(self, model_path: str = "anti_detect/model.json"):
        self.model = None
        self.model_path = Path(model_path)
        self._load_model()
    
    def _load_model(self):
        try:
            import xgboost as xgb
            self.model = xgb.XGBClassifier()
            if self.model_path.exists():
                self.model.load_model(str(self.model_path))
            else:
                self._train_model()
        except ImportError:
            self.model = None
    
    def _train_model(self):
        try:
            import xgboost as xgb
        except ImportError:
            return
        np.random.seed(42)
        n = 1000
        X = np.vstack([np.random.uniform(0, 0.5, (n//2, 12)), np.random.uniform(0.5, 1.0, (n//2, 12))])
        y = np.array([0]*(n//2) + [1]*(n//2))
        self.model = xgb.XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, objective="binary:logistic")
        self.model.fit(X, y)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(self.model_path))
    
    def assess_risk(self, signals: list[float]) -> RiskAssessment:
        if self.model is None:
            return self._rule_based(signals)
        features = np.array(signals).reshape(1, -1)
        risk_prob = self.model.predict_proba(features)[0][1]
        return self._create(int(risk_prob * 100), signals)
    
    def _rule_based(self, signals: list[float]) -> RiskAssessment:
        weights = [0.15, 0.12, 0.15, 0.10, 0.08, 0.08, 0.07, 0.10, 0.05, 0.05, 0.03, 0.02]
        return self._create(int(sum(s*w for s, w in zip(signals, weights)) * 100), signals)
    
    def _create(self, score: int, signals: list[float]) -> RiskAssessment:
        if score < 40: level, rec = "SAFE", "No action needed"
        elif score < 65: level, rec = "CAUTION", "Increase timing noise"
        elif score < 80: level, rec = "WARNING", "Significant noise required"
        else: level, rec = "CRITICAL", "Abort session"
        return RiskAssessment(score=score, level=level, signals_above_threshold=sum(1 for s in signals if s > 0.7), recommendation=rec)
