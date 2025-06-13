import os
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
import torch
# 远程推送器代码已删除，保留占位
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("警告: ultralytics未安装，YOLO检测功能将被禁用")

# 远程推送器功能已移除
REMOTE_PUSHER_AVAILABLE = False

@dataclass
class DetectionResult:
    stream_id: str
    timestamp: float
    frame_path: str
    detections: List[Dict]
    total_objects: int

class YOLODetector:
    def __init__(self, model_path: str = "models/best.pt", 
                 confidence_threshold: float = 0.5,
                 iou_threshold: float = 0.5,
                 device: str = "auto",
                 distributed_manager=None):  # remote_pusher 参数已移除
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        # 自动选择设备
        if device == 'auto':
            self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        self.model = None
        self.class_names = {}
        
        # 分布式推理管理器
        self.distributed_manager = distributed_manager
        self.use_distributed = distributed_manager is not None
        
        # 远程推送器占位
        self.remote_pusher = None

        if YOLO_AVAILABLE and not self.use_distributed:
            # 只有在非分布式模式下才初始化本地模型
            try:
                if os.path.exists(model_path):
                    self.model = YOLO(model_path)
                    self.model.to(self.device)  # 设置设备
                    self.class_names = self.model.names
                    print(f"YOLO模型加载成功: {model_path}, 设备: {self.device}")
                    print(f"📋 YOLO支持的类别数量: {len(self.class_names)}")
                    print(f"🏷️ 支持的类别: {list(self.class_names.values())}")
                else:
                    print(f"警告: YOLO模型文件不存在: {model_path}")
            except Exception as e:
                print(f"YOLO模型加载失败: {e}")
        elif self.use_distributed:
            print(f"🚀 分布式推理模式已启用，将使用远程GPU服务器")
            # 获取类别名称（从已有模型或配置中）
            self._init_class_names()
        
    def _init_class_names(self):
        """初始化类别名称（分布式模式下）"""
        # 默认YOLO类别（可以从配置文件加载）
        self.class_names = {
            0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 4: 'airplane', 
            5: 'bus', 6: 'train', 7: 'truck', 8: 'boat', 9: 'traffic light', 
            10: 'fire hydrant', 11: 'stop sign', 12: 'parking meter', 13: 'bench', 
            14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse', 18: 'sheep', 19: 'cow', 
            20: 'elephant', 21: 'bear', 22: 'zebra', 23: 'giraffe', 24: 'backpack'
        }
        
    def detect(self, stream_id: str, frame: np.ndarray, 
               timestamp: float, risk_config: Optional[Dict] = None) -> DetectionResult:
        """执行目标检测"""
        detections = []
        
        # 分布式推理模式
        if self.use_distributed and self.distributed_manager:
            try:
                print(f"🚀 [分布式推理] 处理帧 {stream_id}")
                # 使用分布式推理
                result = self.distributed_manager.process_frame_sync(
                    stream_id=stream_id,
                    frame=frame,
                    timeout=30.0
                )
                
                if result and 'detections' in result:
                    detections = result['detections']
                    print(f"✅ [分布式推理] 检测到 {len(detections)} 个对象")
                else:
                    print(f"⚠️ [分布式推理] 未获取到有效结果，回退到本地处理")
                    # 回退到本地处理
                    detections = self._detect_locally(frame, risk_config)
                    
            except Exception as e:
                print(f"❌ [分布式推理] 处理失败: {e}")
                print(f"🔄 [回退处理] 使用本地CPU推理")
                # 回退到本地处理
                detections = self._detect_locally(frame, risk_config)
                
        else:
            # 本地推理模式
            detections = self._detect_locally(frame, risk_config)
        
        # 保存检测结果图像
        frame_path = self._save_detection_frame(stream_id, frame, detections, timestamp)
        
        # 创建检测结果
        detection_result = DetectionResult(
            stream_id=stream_id,
            timestamp=timestamp,
            frame_path=frame_path,
            detections=detections,
            total_objects=len(detections)
        )
        
        # 注: 检测服务不再负责推送或业务规则判断，交由上游聚合层处理
        
        return detection_result
    
    def _detect_locally(self, frame: np.ndarray, risk_config: Optional[Dict]) -> List[Dict]:
        """本地检测"""
        detections = []
        
        if self.model is not None:
            try:
                # 执行YOLO检测
                confidence_threshold = risk_config.get('confidence_threshold', self.confidence_threshold) if risk_config else self.confidence_threshold
                results = self.model(
                    frame, 
                    conf=confidence_threshold,
                    iou=self.iou_threshold,
                    verbose=False
                )
                
                # 解析检测结果
                if results and len(results) > 0:
                    result = results[0]
                    
                    if hasattr(result, 'boxes') and result.boxes is not None:
                        boxes = result.boxes
                        
                        for i in range(len(boxes)):
                            # 边界框坐标
                            bbox = boxes.xyxy[i].cpu().numpy()
                            x1, y1, x2, y2 = bbox
                            
                            # 置信度
                            confidence = boxes.conf[i].cpu().numpy()
                            
                            # 类别
                            class_id = int(boxes.cls[i].cpu().numpy())
                            class_name = self.class_names.get(class_id, f'class_{class_id}')
                            
                            # 过滤指定类别（如果配置了）
                            detection_classes = risk_config.get('detection_classes', []) if risk_config else []
                            if detection_classes and class_name not in detection_classes:
                                continue
                            
                            detection = {
                                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                'confidence': float(confidence),
                                'class_id': class_id,
                                'class_name': class_name,
                                'area': float((x2 - x1) * (y2 - y1))
                            }
                            
                            detections.append(detection)
                            
            except Exception as e:
                print(f"YOLO检测错误: {e}")
        
        return detections
    
    def _save_detection_frame(self, stream_id: str, frame: np.ndarray, 
                             detections: List[Dict], timestamp: float) -> str:
        """保存检测结果图像"""
        try:
            # 将结果统一保存到项目根 static/results 目录，便于前端访问
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            results_dir = os.path.join(base_dir, 'static', 'results')
            
            # 确保结果目录存在
            os.makedirs(results_dir, exist_ok=True)
            
            # 绘制检测框
            annotated_frame = frame.copy()
            for detection in detections:
                bbox = detection['bbox']
                x1, y1, x2, y2 = map(int, bbox)
                
                # 绘制边界框
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # 绘制标签
                label = f"{detection['class_name']}: {detection['confidence']:.2f}"
                cv2.putText(annotated_frame, label, (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 保存图像
            filename = f"detection_{stream_id}_{int(timestamp)}.jpg"
            # 绝对路径写盘
            filepath_abs = os.path.join(results_dir, filename)
            cv2.imwrite(filepath_abs, annotated_frame)
            
            # 返回相对 Web 路径，避免在 Windows 上带盘符
            web_path = os.path.join('static', 'results', filename).replace('\\', '/')
            return web_path
        except Exception as e:
            print(f"保存检测图像失败: {e}")
            return ""
    
    # 以下远程推送相关方法已弃用，保留占位符以兼容旧代码调用但不执行任何操作
    def _push_to_remote_server(self, *args, **kwargs):
        return

    def stop_remote_pusher(self):
        return

    def get_remote_pusher_stats(self):
        return None
    
    def is_available(self) -> bool:
        """检查YOLO检测器是否可用"""
        return self.model is not None
    
    def get_supported_classes(self) -> List[str]:
        """获取支持的检测类别"""
        if self.model is not None:
            return list(self.class_names.values())
        return []