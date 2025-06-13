"""threshold_calibrator.py

Online auto‑calibration of pose thresholds.

This daemon thread tracks statistical distributions of selected per‑person
features (e.g., height_ratio, trunk_angle, head_angle) over a sliding window
and updates the corresponding min/max values in `detection_rules.yaml`.

Usage (inside `behavior_model.py`):
    from pathlib import Path
    from threshold_calibrator import ThresholdCalibrator

    calibrator = ThresholdCalibrator(
        rule_file=Path("config/detection_rules.yaml"),
        window=300,
        update_interval=60,
        iqr_tol=0.15,
        rollback_threshold=3,
    )
    calibrator.start()
    self._calibrator = calibrator  # keep reference to stop later if needed

    # later when computing features per frame / per person:
    self._calibrator.add_sample("height_ratio", hr)
    self._calibrator.add_sample("trunk_angle", t_angle)

Notes:
* Thread‑safe queues (deque) avoid locks because `collections.deque` append is GIL‑protected.
* Uses IQR (P25‑P75) with ±tol% to derive new min/max.
* Consecutive spikes exceeding `rollback_threshold` revert to last stable snapshot.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List

import numpy as np
import yaml
import logging

_LOG = logging.getLogger("threshold_calibrator")


class ThresholdCalibrator(threading.Thread):
    """Background thread that learns and updates YAML thresholds."""

    def __init__(
        self,
        rule_file: Path | str,
        *,
        window: int = 300,
        update_interval: int = 60,
        iqr_tol: float = 0.15,
        rollback_threshold: int = 3,
    ) -> None:
        super().__init__(daemon=True)
        self.rule_file = Path(rule_file)
        self.window = window  # number of recent samples retained per feature
        self.update_interval = update_interval
        self.iqr_tol = iqr_tol
        self.rollback_threshold = rollback_threshold

        # FeatureName -> deque of recent float samples
        self._buffers: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )

        # Track previous stable thresholds for potential rollback
        self._prev_stable: Dict[str, Dict[str, float | bool]] = {}
        self._consecutive_spikes: Dict[str, int] = defaultdict(int)

        self._stop_event = threading.Event()

        self._load_rules()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_sample(self, feature_name: str, value: float) -> None:
        """Push a new numeric sample for the given feature."""
        self._buffers[feature_name].append(float(value))

    def stop(self) -> None:
        """Signal thread to stop and wait until it terminates."""
        self._stop_event.set()
        self.join(timeout=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_rules(self) -> None:
        if not self.rule_file.exists():
            raise FileNotFoundError(self.rule_file)
        with self.rule_file.open("r", encoding="utf-8") as fh:
            self._rules = yaml.safe_load(fh)
        # Ensure nested keys exist
        self._rules.setdefault("thresholds", {}).setdefault("pose", {})
        self._pose_thresh = self._rules["thresholds"]["pose"]
        # Store copy as baseline
        self._prev_stable = {
            k: dict(v) for k, v in self._pose_thresh.items() if isinstance(v, dict)
        }

    def run(self) -> None:  # noqa: D401
        while not self._stop_event.is_set():
            # Sleep in small increments so we can respond quickly to stop signal
            self._stop_event.wait(self.update_interval)
            if self._stop_event.is_set():
                break
            self._recompute()
            self._dump_rules()

    # ------------------------------------------------------------------
    def _recompute(self) -> None:
        """Recalculate thresholds for each collected feature."""
        for feat, buf in self._buffers.items():
            if len(buf) < self.window // 2:
                continue  # insufficient data
            q1, q3 = np.percentile(buf, [25, 75])
            new_min = round(q1 * (1 - self.iqr_tol), 4)
            new_max = round(q3 * (1 + self.iqr_tol), 4)

            current = self._pose_thresh.get(feat, {})
            old_min, old_max = current.get("min"), current.get("max")

            # Detect spike: if change exceeds tolerance
            def _exceeds(a: float | None, b: float) -> bool:
                return a is None or abs(a - b) / max(abs(a), 1e-6) > self.iqr_tol

            if _exceeds(old_min, new_min) or _exceeds(old_max, new_max):
                self._consecutive_spikes[feat] += 1
                _LOG.debug(
                    "Potential spike in %s (%.4f..%.4f) vs old %.4f..%.4f (count=%d)",
                    feat,
                    new_min,
                    new_max,
                    old_min,
                    old_max,
                    self._consecutive_spikes[feat],
                )
                if self._consecutive_spikes[feat] >= self.rollback_threshold:
                    # rollback to last good snapshot (if any)
                    snapshot = self._prev_stable.get(feat)
                    if snapshot:
                        self._pose_thresh[feat] = dict(snapshot)
                        _LOG.warning("Rolled back threshold %s -> %s", feat, snapshot)
                    self._consecutive_spikes[feat] = 0
                continue  # wait for window to stabilise

            # Accept new thresholds
            self._pose_thresh[feat] = {
                "min": new_min,
                "max": new_max,
                "auto_calibrated": True,
            }
            self._prev_stable[feat] = dict(self._pose_thresh[feat])
            self._consecutive_spikes[feat] = 0
            _LOG.info("Updated threshold %s = %.4f .. %.4f", feat, new_min, new_max)

    # ------------------------------------------------------------------
    def _dump_rules(self) -> None:
        self._rules["thresholds"]["pose"] = self._pose_thresh
        # Update meta timestamp
        meta = self._rules.setdefault("meta", {})
        meta["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        tmp = self.rule_file.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(
                self._rules,
                fh,
                allow_unicode=True,
                sort_keys=False,
                width=120,
                default_flow_style=False,
            )
        tmp.replace(self.rule_file)
        _LOG.debug("Persisted updated rules to %s", self.rule_file)
