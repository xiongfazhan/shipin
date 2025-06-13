"""summary_payload.py

Data classes + helpers to build the 5‑minute summary payload (v2 schema).
Designed to be imported by `app.py` where the APScheduler job will assemble
object & pose data and push to downstream consumers (WebSocket / Webhook).

Example
-------
>>> from datetime import datetime, timedelta, timezone
>>> from summary_payload import SummaryBuilder
>>> builder = SummaryBuilder(window_start=datetime.now(tz=timezone.utc))
>>> builder.add_object_detection(label="knife", bbox=[10,20,50,70], conf=0.88,
...                              frame_idx=120, image_url="s3://bucket/f0120.jpg")
>>> builder.add_anomaly(event_type="prohibited_item", objects=["o_00"],
...                     severity="high", description="Knife detected", frames=[120])
>>> builder.add_person_action(person_id="p_01", action="stand", conf=0.95, dur=240)
>>> payload = builder.build()
>>> payload_json = payload.to_json()
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# Data classes (serialisable)
# ---------------------------------------------------------------------------

def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


@dataclass
class DetectionWindow:
    start: datetime
    end: datetime

    def to_dict(self) -> Dict[str, str]:
        return {"start": _iso(self.start), "end": _iso(self.end)}


@dataclass
class BasicStats:
    frames: int = 0
    persons: int = 0
    objects: int = 0


@dataclass
class ObjDet:
    id: str
    label: str
    bbox: List[int]
    conf: float
    frame: int
    image_url: str


@dataclass
class AnomalyEvent:
    event_type: str
    objects: List[str] = field(default_factory=list)
    severity: str = "medium"
    description: str = ""
    frames: List[int] = field(default_factory=list)


@dataclass
class ObjectDetectionSection:
    detections: List[ObjDet] = field(default_factory=list)
    anomaly_events: List[AnomalyEvent] = field(default_factory=list)


@dataclass
class PersonAction:
    action: str
    confidence: float
    duration_s: int


@dataclass
class PersonInfo:
    person_id: str
    actions: List[PersonAction]
    key_points: Optional[List[List[float]]] = None


@dataclass
class PoseDetectionSection:
    persons: List[PersonInfo] = field(default_factory=list)


@dataclass
class SummaryPayload:
    window: DetectionWindow
    basic_stats: BasicStats
    object_detection: ObjectDetectionSection
    pose_detection: PoseDetectionSection

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "window": self.window.to_dict(),
            "basic_stats": asdict(self.basic_stats),
            "object_detection": {
                "detections": [asdict(d) for d in self.object_detection.detections],
                "secondary_analysis": {
                    "anomaly_events": [asdict(ev) for ev in self.object_detection.anomaly_events]
                },
            },
            "pose_detection": {
                "persons": [
                    {
                        "person_id": p.person_id,
                        "actions": [asdict(a) for a in p.actions],
                        "key_points": p.key_points,
                    }
                    for p in self.pose_detection.persons
                ]
            },
        }

    def to_json(self, *, compact: bool = True) -> str:
        if compact:
            return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Builder util used by AnalyticsService (app.py)
# ---------------------------------------------------------------------------

class SummaryBuilder:
    """Collects data throughout the window and builds SummaryPayload."""

    def __init__(self, *, window_start: datetime, duration_s: int = 300):
        self._window_start = window_start
        self._window_end = window_start + timedelta(seconds=duration_s)
        self._stats = BasicStats()
        self._obj_section = ObjectDetectionSection()
        self._pose_section = PoseDetectionSection()

    # ---------- stats ----------
    def increment_frames(self, n: int = 1):
        self._stats.frames += n

    def increment_persons(self, n: int = 1):
        self._stats.persons += n

    def increment_objects(self, n: int = 1):
        self._stats.objects += n

    # ---------- object detection ----------
    def add_object_detection(
        self,
        *,
        label: str,
        bbox: List[int],
        conf: float,
        frame_idx: int,
        image_url: str,
        detection_id: Optional[str] = None,
    ) -> str:
        det_id = detection_id or _uid("o")
        det = ObjDet(id=det_id, label=label, bbox=bbox, conf=round(conf, 3), frame=frame_idx, image_url=image_url)
        self._obj_section.detections.append(det)
        return det_id

    def add_anomaly(
        self,
        *,
        event_type: str,
        objects: List[str] | None = None,
        severity: str = "medium",
        description: str = "",
        frames: List[int] | None = None,
    ) -> None:
        ev = AnomalyEvent(
            event_type=event_type,
            objects=objects or [],
            severity=severity,
            description=description,
            frames=frames or [],
        )
        self._obj_section.anomaly_events.append(ev)

    # ---------- pose detection ----------
    def add_person_action(
        self,
        *,
        person_id: str,
        action: str,
        conf: float,
        dur: int,
        key_points: Optional[List[List[float]]] = None,
    ) -> None:
        # Find or create person
        persons = {p.person_id: p for p in self._pose_section.persons}
        if person_id not in persons:
            persons[person_id] = PersonInfo(person_id=person_id, actions=[], key_points=key_points)
            self._pose_section.persons.append(persons[person_id])
        persons[person_id].actions.append(PersonAction(action=action, confidence=round(conf, 3), duration_s=int(dur)))

    # ---------- build ----------
    def build(self) -> SummaryPayload:
        return SummaryPayload(
            window=DetectionWindow(self._window_start, self._window_end),
            basic_stats=self._stats,
            object_detection=self._obj_section,
            pose_detection=self._pose_section,
        )

# ---------------------------------------------------------------------------
# Convenience: functional API (if builder not required)
# ---------------------------------------------------------------------------

def make_summary(
    *,
    window_start: datetime,
    window_end: datetime,
    frames: int,
    persons: int,
    objects: int,
    detections: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    persons_detail: List[Dict[str, Any]],
) -> SummaryPayload:
    """Quick helper when data already aggregated as lists/dicts."""
    obj_section = ObjectDetectionSection(
        detections=[ObjDet(**d) for d in detections],
        anomaly_events=[AnomalyEvent(**ev) for ev in anomalies],
    )
    pose_section = PoseDetectionSection(
        persons=[
            PersonInfo(
                person_id=p["person_id"],
                actions=[PersonAction(**act) for act in p["actions"]],
                key_points=p.get("key_points"),
            )
            for p in persons_detail
        ]
    )

    return SummaryPayload(
        window=DetectionWindow(window_start, window_end),
        basic_stats=BasicStats(frames=frames, persons=persons, objects=objects),
        object_detection=obj_section,
        pose_detection=pose_section,
    )
