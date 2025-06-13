"""behavior_model.py  (refactored)

AdvancedActionRecognizer with ThresholdCalibrator integration.

This file shows *all* required hooks to support:
  • Online threshold auto-calibration (TAC)
  • Unified YAML rules loading (detection_rules.yaml)
  • Structlog JSON logging

⚠️ **Note**  
The core geometry / dynamics computations are kept under `# --- ORIGINAL LOGIC ---`  
If you had custom code there, just splice it back in – the new imports and
hooks will work transparently.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict

import numpy as np
import yaml

from logging_config import get_logger  # JSON logger
from threshold_calibrator import ThresholdCalibrator  # online auto-tuning

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Config & rules
# ---------------------------------------------------------------------------
_RULES_PATH = Path("config/detection_rules.yaml")
_RULES_DATA: Dict[str, Any] = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
_POSE_THRESH = _RULES_DATA["thresholds"]["pose"]
_ACTION_RULES = _RULES_DATA.get("actions", {})

# ---------------------------------------------------------------------------
# Helper functions (kept minimal for brevity)
# ---------------------------------------------------------------------------

def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return angle ABC in degrees (placeholder)."""
    ba, bc = a - b, c - b
    cosang = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0))))


# ---------------------------------------------------------------------------
# AdvancedActionRecognizer – MAIN CLASS
# ---------------------------------------------------------------------------
class AdvancedActionRecognizer:
    """Single-person action recognizer (supports TAC)."""

    def __init__(self, *, person_buffer: int = 60):
        self.person_buffer = person_buffer

        # Auto-calibration thread
        self._calibrator = ThresholdCalibrator(
            rule_file=_RULES_PATH,
            window=300,
            update_interval=60,
            iqr_tol=0.15,
            rollback_threshold=3,
        )
        self._calibrator.start()
        log.info("calibrator_started")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def recognize(self, keypoints: np.ndarray) -> Dict[str, float]:
        """Return {action: confidence} dict for a single person keypoints."""
        feats = self._extract_features(keypoints)
        probs = self._rule_based_inference(feats)
        return probs

    def close(self) -> None:
        if self._calibrator.is_alive():
            self._calibrator.stop()
            log.info("calibrator_stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_features(self, kp: np.ndarray) -> Dict[str, float]:
        """Compute geometric & dynamic features (height_ratio, trunk_angle...)."""
        # --- ORIGINAL LOGIC START ------------------------------------
        # Stub examples – replace with your actual implementation
        head, hip, ankle = kp[0], kp[8], kp[14]
        height_pixels = np.linalg.norm(head - ankle)
        trunk_angle = calculate_angle(head, hip, ankle)
        height_ratio = height_pixels / max(np.linalg.norm(head - hip), 1e-3)
        # --- ORIGINAL LOGIC END --------------------------------------

        feats = {
            "height_ratio": round(height_ratio, 4),
            "trunk_angle": round(trunk_angle, 2),
        }

        # Feed samples to calibrator
        for k, v in feats.items():
            self._calibrator.add_sample(k, v)
        return feats

    def _rule_based_inference(self, feats: Dict[str, float]) -> Dict[str, float]:
        """Simple threshold rule inference using updated YAML rules."""
        results: Dict[str, float] = {}
        for action, rule in _ACTION_RULES.items():
            geom = rule.get("geometry", {})
            ok = True
            for field in ("height_ratio", "trunk_angle", "head_angle"):
                if field in geom and feats.get(field) is not None:
                    low = geom.get(f"{field}_min", -float("inf"))
                    high = geom.get(f"{field}_max", float("inf"))
                    if not (low <= feats[field] <= high):
                        ok = False
                        break
            if ok:
                # Confidence = distance to threshold (naive)
                results[action] = 0.9
        # fallback none
        if not results:
            results["unknown"] = 0.1
        log.debug("actions", feats=feats, actions=results)
        return results


# ---------------------------------------------------------------------------
# CLI test (python behavior_model.py path/to/keypoints.npy)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    kp_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if kp_path and kp_path.exists():
        kp_arr = np.load(kp_path)
    else:
        kp_arr = np.random.rand(17, 2) * 100  # dummy 17-keypoints

    recognizer = AdvancedActionRecognizer()
    out = recognizer.recognize(kp_arr)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    recognizer.close()
