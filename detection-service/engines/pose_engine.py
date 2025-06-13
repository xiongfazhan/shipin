from typing import Dict, List, Any
import numpy as np
from .base import BaseEngine

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class PoseEngine(BaseEngine):
    """基于 YOLOv8 Pose 的多人关键点检测引擎（简化版）"""

    def __init__(self, model_path: str, device: str = "cpu", confidence_threshold: float = 0.5, iou_threshold: float = 0.7, **kwargs):
        super().__init__()
        if not YOLO_AVAILABLE:
            raise RuntimeError("ultralytics 库未安装，无法启用 PoseEngine")
        self.model = YOLO(model_path)
        self.model.to(device)
        self.device = device
        self.conf = confidence_threshold
        self.iou = iou_threshold

    def infer(self, stream_id: str, frame: np.ndarray, timestamp: float, config: Dict) -> List[Dict[str, Any]]:
        results = self.model(frame, conf=self.conf, iou=self.iou, verbose=False)
        poses: List[Dict[str, Any]] = []
        if results:
            res = results[0]
            if res.keypoints is not None:
                boxes = res.boxes
                keypoints = res.keypoints
                for i in range(len(keypoints.data)):
                    # 提取关键点 (17,3) -> list[51]
                    kpt = keypoints.data[i].cpu().numpy().flatten().tolist()
                    bbox = None
                    if boxes is not None and i < len(boxes.data):
                        bbox = boxes.data[i][:4].cpu().numpy().tolist()  # x1,y1,x2,y2
                        conf_val = float(boxes.data[i][4].cpu().numpy())
                    else:
                        conf_val = 0.0
                    pose_item = {
                        'person_index': i,
                        'keypoints': kpt,
                        'bbox': bbox,
                        'confidence': conf_val
                    }
                    poses.append(pose_item)
        return [{
            'algo_type': 'pose',
            'stream_id': stream_id,
            'timestamp': timestamp,
            'model': 'yolov8-pose',
            'device': self.device,
            'poses': poses,
            'total_persons': len(poses)
        }] 