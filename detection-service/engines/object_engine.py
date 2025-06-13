from typing import Dict, List, Any
import time
import numpy as np

from modules.yolo_detector import YOLODetector
from .base import BaseEngine


class ObjectEngine(BaseEngine):
    """基于 YOLODetector 的目标检测引擎"""

    def __init__(self, model_path: str, device: str = "auto", confidence_threshold: float = 0.5, iou_threshold: float = 0.45, **kwargs):
        super().__init__()
        self.detector = YOLODetector(
            model_path=model_path,
            device=device,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold
        )

    def infer(self, stream_id: str, frame: np.ndarray, timestamp: float, config: Dict) -> List[Dict[str, Any]]:
        detection_res = self.detector.detect(stream_id=stream_id, frame=frame, timestamp=timestamp, risk_config=config)

        # 转换为通用 schema
        return [{
            'algo_type': 'object',
            'stream_id': stream_id,
            'timestamp': timestamp,
            'detection_id': f"{stream_id}_{int(timestamp * 1000)}",
            'model': self.detector.model_path,
            'device': self.detector.device,
            'detections': detection_res.detections,
            'total_objects': detection_res.total_objects,
            'frame_path': detection_res.frame_path
        }] 