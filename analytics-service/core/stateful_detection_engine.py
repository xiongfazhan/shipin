"""stateful_detection_engine.py  (refactored)

Minimal adjustments:
  • Load unified detection_rules.yaml
  • Use structlog JSON logging
  • Provide accessors get_event_rules(), get_pose_thresholds()

The core FSM/event evaluation logic from your original file can be kept as‑is.
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from logging_config import get_logger

log = get_logger(__name__)
_RULES_PATH = Path("config/detection_rules.yaml")
_RULES: Dict[str, Any] = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
_EVENT_RULES = _RULES.get("events", {})
_POSE_THRESH = _RULES["thresholds"]["pose"]


# ---------------------------------------------------------------------------
# Helper accessors (others can import instead of re‑reading file)
# ---------------------------------------------------------------------------

def get_event_rules() -> Dict[str, Any]:
    return _EVENT_RULES


def get_pose_thresholds() -> Dict[str, Any]:
    return _POSE_THRESH


# ---------------------------------------------------------------------------
# Core Engine skeleton – keep original logic below
# ---------------------------------------------------------------------------
class SessionState:
    """Holds per‑ID buffers (simplified)."""

    def __init__(self, *, ttl_s: int = 600):
        self.frames: deque[Any] = deque(maxlen=1000)
        self.last_seen: float = time.time()
        self.ttl_s = ttl_s
        self.detected_events: Dict[str, datetime] = {}

    def add_frame(self, frame_data: Dict[str, Any]):
        self.frames.append(frame_data)
        self.last_seen = time.time()


class StatefulDetectionEngine:
    """Evaluates rules over time windows – simplified placeholder."""

    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self._cleanup_interval = 60
        log.info("engine_init", rules=len(_EVENT_RULES))

    # ------------------------------------------------------------------
    def process(self, trace_id: str, frame_data: Dict[str, Any]):
        """Entry point called every frame (by inference node or service)."""
        sess = self.sessions.setdefault(trace_id, SessionState())
        sess.add_frame(frame_data)
        self._evaluate(sess, frame_data)

    # ------------------------------------------------------------------
    def _evaluate(self, sess: SessionState, frame_data: Dict[str, Any]):
        """Iterate over rules & emit events (placeholder)."""
        ts = datetime.now(tz=timezone.utc)
        for name, rule in _EVENT_RULES.items():
            # --- ORIGINAL rule evaluation logic here ---
            pass  # keep your detailed FSM checks

    # ------------------------------------------------------------------
    def cleanup(self):
        now = time.time()
        pruned = [k for k, v in self.sessions.items() if now - v.last_seen > v.ttl_s]
        for k in pruned:
            del self.sessions[k]
        if pruned:
            log.debug("session_cleanup", removed=len(pruned))
