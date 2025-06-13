"""yolo_multiperson_demo.py  (refactored)

Adds:
  • structlog JSON logging
  • global trace_id per run, injected into POST payloads
  • requests retry session

*Inference / drawing code trimmed for brevity – plug back your original.*
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
import requests
from requests.adapters import HTTPAdapter, Retry

from logging_config import get_logger

log = get_logger(__name__)
API_ENDPOINT = "http://localhost:8000/api/events/detection"
trace_id = uuid.uuid4().hex[:8]

# Robust HTTP session
_session = requests.Session()
_session.mount(
    "http://",
    HTTPAdapter(max_retries=Retry(total=3, backoff_factor=0.3, status_forcelist=[502, 503, 504])),
)

# ---------------------------------------------------------------------------
# Load YOLOv8‑Pose model (placeholder)
# ---------------------------------------------------------------------------

def load_model(weights: str | Path = "yolov8n‑pose.pt") -> Any:  # noqa: ANN401
    log.info("loading_model", weights=str(weights))
    # TODO: Replace with ultralytics or your wrapper
    return None


# ---------------------------------------------------------------------------
# Main loop (simplified)
# ---------------------------------------------------------------------------

def run(video_path: str | Path):
    model = load_model()
    cap = cv2.VideoCapture(str(video_path))
    idx = 0
    start_ts = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        idx += 1

        # --- ORIGINAL INFERENCE LOGIC HERE ---------------------------
        # Assume we get detections: objects[], persons[], anomalies[]
        objects: list[Dict[str, Any]] = []  # fill with your yolo output
        persons: list[Dict[str, Any]] = []  # fill with pose output
        anomalies: list[Dict[str, Any]] = []
        # ------------------------------------------------------------------

        payload = {
            "trace_id": trace_id,
            "frame_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "frame_idx": idx,
            "objects": objects,
            "persons": persons,
            "anomalies": anomalies,
        }
        try:
            _session.post(API_ENDPOINT, json=payload, timeout=1.5)
        except requests.RequestException as exc:  # noqa: BLE001
            log.warning("push_fail", error=str(exc))

        if idx % 100 == 0:
            fps = idx / (time.time() - start_ts + 1e-6)
            log.info("progress", frames=idx, fps=round(fps, 2))

    cap.release()
    log.info("finished", frames=idx)


if __name__ == "__main__":
    import sys

    vid = sys.argv[1] if len(sys.argv) > 1 else 0  # 0 == webcam
    run(vid)
