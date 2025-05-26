import cv2
import numpy as np
import threading
import time
import queue
from datetime import datetime
import os

# 模拟YOLO模型（稍后可替换为实际的YOLO模型）
class YOLOModel:
    """YOLO模型封装类"""
    
    def __init__(self, model_path=None, conf_threshold=0.5, nms_threshold=0.4):
        """初始化YOLO模型
        
        Args:
            model_path: 模型权重路径
            conf_threshold: 置信度阈值
            nms_threshold: 非极大值抑制阈值
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.classes = self._load_classes()
        self.model = self._load_model()
        self.initialized = True
        
        print(f"YOLO模型已初始化，类别数: {len(self.classes)}")
    
    def _load_classes(self):
        """加载目标类别"""
        # COCO数据集的80个类别
        return [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
            'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
            'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
            'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
            'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
            'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
            'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
            'toothbrush'
        ]
    
    def _load_model(self):
        """加载YOLO模型"""
        # 在此处实现实际的模型加载代码
        # 例如：使用OpenCV的DNN模块或直接使用PyTorch/TensorFlow
        
        # 返回一个模拟的模型对象
        return "模拟YOLO模型"
    
    def detect(self, image):
        """检测图像中的对象
        
        Args:
            image: 输入图像（OpenCV格式）
            
        Returns:
            list: 检测结果列表，每个元素是 (类别ID, 置信度, [x, y, w, h])
        """
        # 模拟随机检测结果
        height, width = image.shape[:2]
        
        # 确保结果的一致性
        np.random.seed(int(sum(image[0, 0]) * 1000) % 10000)
        
        # 随机生成检测结果数量
        num_detections = np.random.randint(0, 5)
        results = []
        
        for _ in range(num_detections):
            # 随机类别ID
            class_id = np.random.randint(0, len(self.classes))
            # 随机置信度
            confidence = np.random.uniform(0.5, 0.95)
            
            # 随机边界框
            x = np.random.randint(0, width - 100)
            y = np.random.randint(0, height - 100)
            w = np.random.randint(50, min(200, width - x))
            h = np.random.randint(50, min(200, height - y))
            
            results.append((class_id, confidence, [x, y, w, h]))
        
        return results
    
    def get_class_name(self, class_id):
        """根据类别ID获取类别名称"""
        if 0 <= class_id < len(self.classes):
            return self.classes[class_id]
        return "unknown"


# 二次检测目标类别（需要进行二次检测的对象）
SECONDARY_DETECTION_CLASSES = ['dining table', 'desk', 'table']

# 创建全局YOLO模型实例
main_model = None
secondary_model = None
model_lock = threading.Lock()

# 二次检测的配置
secondary_detection_config = {
    'enabled': True,  # 是否启用二次检测
    'target_classes': SECONDARY_DETECTION_CLASSES,  # 触发二次检测的类别
    'conf_threshold': 0.4,  # 二次检测的置信度阈值
}

# 保存检测结果的队列
detection_results_queue = queue.Queue(maxsize=100)

def initialize_models():
    """初始化YOLO模型"""
    global main_model, secondary_model
    
    with model_lock:
        if main_model is None:
            print("初始化主YOLO模型...")
            main_model = YOLOModel(conf_threshold=0.5)
        
        if secondary_model is None:
            print("初始化二次检测YOLO模型...")
            secondary_model = YOLOModel(conf_threshold=secondary_detection_config['conf_threshold'])
    
    return main_model is not None and secondary_model is not None

def detect_objects(frame, video_id, timestamp):
    """检测图像中的对象
    
    实现主检测和二次检测逻辑
    
    Args:
        frame: 输入图像
        video_id: 视频流ID
        timestamp: 时间戳
        
    Returns:
        dict: 检测结果，包含主检测和二次检测信息
    """
    if not initialize_models():
        return {
            'video_id': video_id,
            'timestamp': timestamp,
            'detections': [],
            'error': '模型初始化失败'
        }
    
    try:
        # 主检测
        primary_detections = main_model.detect(frame)
        
        all_detections = []
        secondary_detection_regions = []
        
        # 处理主检测结果
        for class_id, confidence, bbox in primary_detections:
            class_name = main_model.get_class_name(class_id)
            
            detection = {
                'class_id': class_id,
                'class_name': class_name,
                'confidence': float(confidence),
                'bbox': bbox,
                'detection_type': 'primary'
            }
            all_detections.append(detection)
            
            # 检查是否需要二次检测
            if (secondary_detection_config['enabled'] and 
                class_name in secondary_detection_config['target_classes']):
                secondary_detection_regions.append((class_name, bbox))
        
        # 进行二次检测
        for parent_class, parent_bbox in secondary_detection_regions:
            x, y, w, h = parent_bbox
            
            # 提取感兴趣区域
            roi = frame[y:y+h, x:x+w].copy()
            
            if roi.size == 0:
                continue
                
            # 对ROI进行检测
            secondary_detections = secondary_model.detect(roi)
            
            # 将局部坐标转换为全局坐标
            for class_id, confidence, local_bbox in secondary_detections:
                class_name = secondary_model.get_class_name(class_id)
                
                # 计算全局坐标
                lx, ly, lw, lh = local_bbox
                global_bbox = [x + lx, y + ly, lw, lh]
                
                # 添加为二次检测结果
                detection = {
                    'class_id': class_id,
                    'class_name': class_name,
                    'confidence': float(confidence),
                    'bbox': global_bbox,
                    'detection_type': 'secondary',
                    'parent_class': parent_class,
                    'parent_bbox': parent_bbox
                }
                
                all_detections.append(detection)
        
        # 组织最终结果
        result = {
            'video_id': video_id,
            'timestamp': timestamp,
            'frame_shape': frame.shape[:2],  # 高度和宽度
            'detections': all_detections,
            'detection_count': len(all_detections)
        }
        
        # 将结果加入队列，供后续处理
        try:
            detection_results_queue.put(result, block=False)
        except queue.Full:
            print("检测结果队列已满，丢弃结果")
        
        return result
        
    except Exception as e:
        print(f"检测过程中出错: {e}")
        return {
            'video_id': video_id,
            'timestamp': timestamp,
            'detections': [],
            'error': str(e)
        }

def process_detection_result(result):
    """处理和保存检测结果
    
    根据配置的规则决定是否保存检测结果
    
    Args:
        result: 检测结果字典
        
    Returns:
        bool: 是否保存成功
    """
    from .database import get_db_connection
    
    if not result or 'error' in result or not result.get('detections', []):
        # 无检测结果或有错误时不保存
        return False
    
    video_id = result.get('video_id', '')
    timestamp = result.get('timestamp', datetime.now())
    detections = result.get('detections', [])
    detection_count = len(detections)
    
    # 存储时间戳为标准化格式字符串
    if isinstance(timestamp, datetime):
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')
    else:
        timestamp_str = str(timestamp)
    
    # 保存检测结果到数据库
    try:
        # 获取数据库连接
        db = get_db_connection()
        cursor = db.cursor()
        
        # 创建检测结果主记录
        cursor.execute("""
            INSERT INTO detection_results 
            (video_id, timestamp, frame_path, detection_count)
            VALUES (?, ?, ?, ?)
        """, (video_id, timestamp_str, None, detection_count))
        
        # 获取刚插入的结果ID
        result_id = cursor.lastrowid
        
        # 保存每个检测对象的详情
        for det in detections:
            class_id = det.get('class_id', 0)
            class_name = det.get('class_name', 'unknown')
            confidence = det.get('confidence', 0.0)
            bbox = det.get('bbox', [0, 0, 0, 0])
            detection_type = det.get('detection_type', 'primary')
            parent_class = det.get('parent_class', None)
            parent_bbox = str(det.get('parent_bbox', None)) if det.get('parent_bbox') else None
            
            # 解析边界框坐标
            bbox_x, bbox_y, bbox_width, bbox_height = bbox
            
            cursor.execute("""
                INSERT INTO detection_objects
                (result_id, class_id, class_name, confidence, 
                 bbox_x, bbox_y, bbox_width, bbox_height,
                 detection_type, parent_class, parent_bbox)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, class_id, class_name, confidence, 
                bbox_x, bbox_y, bbox_width, bbox_height,
                detection_type, parent_class, parent_bbox
            ))
        
        # 提交事务
        db.commit()
        print(f"已保存检测结果: ID={result_id}, 视频={video_id}, 检测对象数={detection_count}")
        return True
        
    except Exception as e:
        print(f"保存检测结果时出错: {e}")
        return False

def draw_detection_boxes(image, result, draw_labels=True):
    """在图像上绘制检测框
    
    Args:
        image: 输入图像
        result: 检测结果
        draw_labels: 是否绘制标签
    
    Returns:
        np.ndarray: 带检测框的图像
    """
    output = image.copy()
    
    # 主检测绘制为绿色框
    primary_color = (0, 255, 0)  # BGR格式
    # 二次检测绘制为蓝色框
    secondary_color = (255, 0, 0)  # BGR格式
    
    for detection in result['detections']:
        bbox = detection['bbox']
        x, y, w, h = [int(v) for v in bbox]
        
        # 确定框的颜色
        color = secondary_color if detection['detection_type'] == 'secondary' else primary_color
        
        # 绘制边界框
        cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)
        
        if draw_labels:
            # 准备标签文本
            label = f"{detection['class_name']} {detection['confidence']:.2f}"
            
            # 计算标签大小
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            
            # 确保标签在图像内部
            label_y = max(y - 10, label_height)
            
            # 绘制标签背景
            cv2.rectangle(
                output,
                (x, label_y - label_height),
                (x + label_width, label_y + baseline),
                color,
                cv2.FILLED
            )
            
            # 绘制标签文本
            cv2.putText(
                output,
                label,
                (x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1
            )
    
    return output

def save_annotated_frame(frame, result, output_dir="detection_results", update_db=True):
    """保存带标注的检测结果图像
    
    Args:
        frame: 原始图像
        result: 检测结果
        output_dir: 输出目录
        update_db: 是否更新数据库中的图像路径
        
    Returns:
        str: 保存的文件路径，失败返回None
    """
    from .database import get_db_connection
    
    try:
        # 获取当前目录（utils）的上一级目录（controller）
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 确保是绝对路径
        if not os.path.isabs(output_dir):
            # 如果是相对路径，则将其转换为绝对路径（基于instance目录）
            output_dir = os.path.join(base_dir, "instance", output_dir)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        if isinstance(result['timestamp'], datetime):
            timestamp_str = result['timestamp'].strftime("%Y%m%d_%H%M%S_%f")
        else:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        video_id = result['video_id']
        filename = f"{video_id}_{timestamp_str}.jpg"
        filepath = os.path.join(output_dir, filename)
        
        # 绘制检测框
        annotated_frame = draw_detection_boxes(frame, result)
        
        # 保存图像
        success = cv2.imwrite(filepath, annotated_frame)
        if not success:
            print(f"OpenCV无法保存图像到: {filepath}")
            # 尝试使用其他方法保存
            from PIL import Image
            import numpy as np
            img = Image.fromarray(cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB))
            img.save(filepath)
            print(f"使用PIL成功保存图像: {filepath}")
        
        print(f"保存检测结果图像: {filepath} 成功: {os.path.exists(filepath)}")
        
        # 如果需要，更新数据库中的图像路径
        if update_db and 'result_id' in result:
            try:
                db = get_db_connection()
                cursor = db.cursor()
                # 存储相对路径，方便后续访问
                relative_path = os.path.join("results", filename)
                cursor.execute(
                    "UPDATE detection_results SET frame_path = ? WHERE result_id = ?",
                    (relative_path, result['result_id'])
                )
                db.commit()
                print(f"已更新检测结果 {result['result_id']} 的图像路径为 {relative_path}")
            except Exception as db_error:
                print(f"更新数据库中的图像路径失败: {db_error}")
                print(f"错误详情: {str(db_error)}")
        
        return filepath
    except Exception as e:
        import traceback
        print(f"保存标注图像失败: {e}")
        traceback.print_exc()
        return None

# 启动时初始化模型
initialize_models() 