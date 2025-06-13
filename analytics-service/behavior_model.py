"""
高精度姿态动作识别系统
基于几何特征和动态时序分析的专业动作识别算法

作者: AI算法专家团队
版本: 2.0 - 精准几何识别版
"""

import numpy as np
import yaml
import math
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
from collections import deque
import cv2
from abc import ABC, abstractmethod
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GeometricFeatures:
    """几何特征数据类"""
    height_normalized: float
    height_pixels: float
    knee_angles: Tuple[float, float]  # 左膝，右膝
    trunk_angle: float
    shoulder_hip_alignment: float
    hip_knee_offset: float
    y_variance: float
    head_drop: float
    neck_angle: float
    
@dataclass
class DynamicFeatures:
    """动态特征数据类"""
    stability_variance: float
    movement_speed: float
    consecutive_frames: int
    nod_count: int
    head_movement_amplitude: float

@dataclass
class PersonState:
    """个人状态追踪"""
    person_id: int
    history_buffer: deque = field(default_factory=lambda: deque(maxlen=60))
    action_counters: Dict[str, int] = field(default_factory=dict)
    last_action: str = "unknown"
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    geometric_history: deque = field(default_factory=lambda: deque(maxlen=30))
    nod_detection_buffer: deque = field(default_factory=lambda: deque(maxlen=30))

class GeometryCalculator:
    """高精度几何计算器"""
    
    @staticmethod
    def calculate_angle_3points(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        """
        计算三点角度 (使用余弦定理)
        p2为顶点，计算∠p1-p2-p3
        """
        try:
            # 构建向量
            v1 = p1 - p2
            v2 = p3 - p2
            
            # 计算向量长度
            len_v1 = np.linalg.norm(v1)
            len_v2 = np.linalg.norm(v2)
            
            if len_v1 == 0 or len_v2 == 0:
                return 0.0
            
            # 余弦值
            cos_angle = np.dot(v1, v2) / (len_v1 * len_v2)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            
            # 转换为角度
            angle_rad = np.arccos(cos_angle)
            angle_deg = np.degrees(angle_rad)
            
            return angle_deg
        except:
            return 0.0
    
    @staticmethod
    def calculate_distance(p1: np.ndarray, p2: np.ndarray) -> float:
        """计算两点欧式距离"""
        return np.linalg.norm(p1 - p2)
    
    @staticmethod
    def normalize_height(keypoints: np.ndarray, config: dict) -> Tuple[float, float]:
        """
        身高归一化计算
        返回: (归一化高度, 像素高度)
        """
        try:
            # 获取关键点
            nose = keypoints[0]
            left_ankle = keypoints[15]
            right_ankle = keypoints[16]
            
            # 脚踝平均位置
            ankle_avg_y = (left_ankle[1] + right_ankle[1]) / 2
            nose_y = nose[1]
            
            # 像素高度
            height_pixels = abs(ankle_avg_y - nose_y)
            
            # 简单归一化 (可根据实际情况调整基准值)
            height_normalized = height_pixels / 140.0  # 假设标准身高140px
            
            return height_normalized, height_pixels
            
        except:
            return 0.0, 0.0

class AdvancedActionRecognizer:
    """高级动作识别器 - 基于几何和动态特征"""
    
    def __init__(self, config_path: str = 'rule_config.yaml'):
        """初始化识别器"""
        self.config = self._load_config(config_path)
        self.geometry_calc = GeometryCalculator()
        
        # 多人状态追踪
        self.person_states: Dict[int, PersonState] = {}
        
        # 观察者模式
        self.observers = []
        
        logger.info("高精度动作识别器初始化完成")
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except:
            logger.error(f"配置文件加载失败: {config_path}")
            return {}
    
    def add_observer(self, observer):
        """添加观察者"""
        self.observers.append(observer)
    
    def notify_observers(self, event_data: dict):
        """通知观察者"""
        for observer in self.observers:
            try:
                observer.on_action_detected(event_data)
            except:
                pass
    
    def extract_geometric_features(self, keypoints: np.ndarray) -> GeometricFeatures:
        """提取几何特征"""
        try:
            # 关键点映射
            kp_idx = self.config['global_params']['keypoint_indices']
            
            # 基础点位
            nose = keypoints[kp_idx['nose']]
            left_shoulder = keypoints[kp_idx['left_shoulder']]
            right_shoulder = keypoints[kp_idx['right_shoulder']]
            left_hip = keypoints[kp_idx['left_hip']]
            right_hip = keypoints[kp_idx['right_hip']]
            left_knee = keypoints[kp_idx['left_knee']]
            right_knee = keypoints[kp_idx['right_knee']]
            left_ankle = keypoints[kp_idx['left_ankle']]
            right_ankle = keypoints[kp_idx['right_ankle']]
            
            # 计算身高归一化
            height_norm, height_pixels = self.geometry_calc.normalize_height(keypoints, self.config)
            
            # 计算膝盖角度 θ_knee = angle(hip, knee, ankle)
            left_knee_angle = self.geometry_calc.calculate_angle_3points(
                left_hip[:2], left_knee[:2], left_ankle[:2]
            )
            right_knee_angle = self.geometry_calc.calculate_angle_3points(
                right_hip[:2], right_knee[:2], right_ankle[:2]
            )
            
            # 计算躯干角度 θ_trunk = angle(shoulder, hip, ankle)
            shoulder_avg = (left_shoulder[:2] + right_shoulder[:2]) / 2
            hip_avg = (left_hip[:2] + right_hip[:2]) / 2
            ankle_avg = (left_ankle[:2] + right_ankle[:2]) / 2
            
            trunk_angle = self.geometry_calc.calculate_angle_3points(
                shoulder_avg, hip_avg, ankle_avg
            )
            
            # 肩髋对齐度 |shoulder_x_avg - hip_x_avg|
            shoulder_x_avg = (left_shoulder[0] + right_shoulder[0]) / 2
            hip_x_avg = (left_hip[0] + right_hip[0]) / 2
            shoulder_hip_alignment = abs(shoulder_x_avg - hip_x_avg)
            
            # 臀膝高度差
            knee_y_avg = (left_knee[1] + right_knee[1]) / 2
            hip_y_avg = (left_hip[1] + right_hip[1]) / 2
            hip_knee_offset = knee_y_avg - hip_y_avg  # 正值表示膝盖低于臀部
            
            # Y坐标方差
            all_y_coords = keypoints[:, 1]
            y_variance = np.std(all_y_coords[all_y_coords > 0])
            
            # 头部下垂 head_drop = nose_y - shoulder_y_avg
            shoulder_y_avg = (left_shoulder[1] + right_shoulder[1]) / 2
            head_drop = nose[1] - shoulder_y_avg
            
            # 颈部角度 (眼-肩连线与垂直线夹角)
            left_eye = keypoints[kp_idx['left_eye']]
            right_eye = keypoints[kp_idx['right_eye']]
            eye_avg = (left_eye[:2] + right_eye[:2]) / 2
            
            # 计算眼-肩向量与垂直向量的角度
            eye_shoulder_vector = eye_avg - shoulder_avg
            vertical_vector = np.array([0, -1])  # 垂直向上
            
            if np.linalg.norm(eye_shoulder_vector) > 0:
                cos_neck = np.dot(eye_shoulder_vector, vertical_vector) / np.linalg.norm(eye_shoulder_vector)
                cos_neck = np.clip(cos_neck, -1.0, 1.0)
                neck_angle = np.degrees(np.arccos(cos_neck))
            else:
                neck_angle = 0.0
            
            return GeometricFeatures(
                height_normalized=height_norm,
                height_pixels=height_pixels,
                knee_angles=(left_knee_angle, right_knee_angle),
                trunk_angle=trunk_angle,
                shoulder_hip_alignment=shoulder_hip_alignment,
                hip_knee_offset=hip_knee_offset,
                y_variance=y_variance,
                head_drop=head_drop,
                neck_angle=neck_angle
            )
            
        except Exception as e:
            logger.error(f"几何特征提取失败: {e}")
            return GeometricFeatures(0, 0, (0, 0), 0, 0, 0, 0, 0, 0)
    
    def analyze_dynamic_features(self, person_state: PersonState, 
                               current_features: GeometricFeatures) -> DynamicFeatures:
        """分析动态特征"""
        try:
            # 添加当前特征到历史记录
            person_state.geometric_history.append(current_features)
            
            if len(person_state.geometric_history) < 5:
                return DynamicFeatures(0, 0, 0, 0, 0)
            
            # 稳定性方差分析 (高度和角度的标准差)
            recent_heights = [f.height_pixels for f in list(person_state.geometric_history)[-10:]]
            recent_trunk_angles = [f.trunk_angle for f in list(person_state.geometric_history)[-10:]]
            
            height_std = np.std(recent_heights) if len(recent_heights) > 1 else 0
            angle_std = np.std(recent_trunk_angles) if len(recent_trunk_angles) > 1 else 0
            stability_variance = height_std + angle_std
            
            # 移动速度计算
            if len(person_state.geometric_history) >= 2:
                prev_features = list(person_state.geometric_history)[-2]
                movement_speed = abs(current_features.height_pixels - prev_features.height_pixels)
            else:
                movement_speed = 0
            
            # 点头检测
            person_state.nod_detection_buffer.append(current_features.head_drop)
            nod_count = self._detect_nod_pattern(person_state.nod_detection_buffer)
            
            # 头部移动幅度
            if len(person_state.nod_detection_buffer) > 1:
                head_positions = list(person_state.nod_detection_buffer)
                head_movement_amplitude = max(head_positions) - min(head_positions)
            else:
                head_movement_amplitude = 0
            
            return DynamicFeatures(
                stability_variance=stability_variance,
                movement_speed=movement_speed,
                consecutive_frames=0,  # 在动作识别中计算
                nod_count=nod_count,
                head_movement_amplitude=head_movement_amplitude
            )
            
        except Exception as e:
            logger.error(f"动态特征分析失败: {e}")
            return DynamicFeatures(0, 0, 0, 0, 0)
    
    def _detect_nod_pattern(self, head_drop_buffer: deque) -> int:
        """检测点头模式"""
        if len(head_drop_buffer) < 10:
            return 0
        
        head_positions = list(head_drop_buffer)
        nod_count = 0
        
        # 检测波峰波谷模式
        for i in range(1, len(head_positions) - 1):
            if (head_positions[i] > head_positions[i-1] and 
                head_positions[i] > head_positions[i+1] and
                head_positions[i] - min(head_positions[i-1], head_positions[i+1]) > 15):
                nod_count += 1
        
        return nod_count
    
    def recognize_action_stand(self, geo_features: GeometricFeatures, 
                             dyn_features: DynamicFeatures) -> Tuple[bool, float]:
        """
        站立动作识别
        条件: H_norm > 0.8 and θ_knee > 165 and θ_trunk > 150 
              and |shoulder_x_avg - hip_x_avg| < 20 
              and std_dev < eps and consecutive_frames > 30
        """
        config = self.config['actions']['站立']
        
        # 静态几何特征检查
        height_ok = (geo_features.height_normalized > config['geometry']['height_ratio_min'] and
                    geo_features.height_pixels > config['geometry']['height_min_pixels'])
        
        knee_ok = (geo_features.knee_angles[0] > config['geometry']['knee_angle_min'] and
                  geo_features.knee_angles[1] > config['geometry']['knee_angle_min'])
        
        trunk_ok = geo_features.trunk_angle > config['geometry']['trunk_angle_min']
        
        alignment_ok = geo_features.shoulder_hip_alignment < config['geometry']['shoulder_hip_align_max']
        
        # 动态稳定性检查
        stability_ok = dyn_features.stability_variance < config['dynamics']['variance_threshold']
        
        # 计算综合置信度
        confidence = 0.0
        if height_ok: confidence += 0.25
        if knee_ok: confidence += 0.3
        if trunk_ok: confidence += 0.25
        if alignment_ok: confidence += 0.1
        if stability_ok: confidence += 0.1
        
        # 所有条件满足才认为是站立
        is_stand = height_ok and knee_ok and trunk_ok and alignment_ok and stability_ok
        
        return is_stand, confidence
    
    def recognize_action_sit(self, geo_features: GeometricFeatures, 
                           dyn_features: DynamicFeatures) -> Tuple[bool, float]:
        """
        坐着动作识别
        条件: 0.5 < H_norm < 0.8 and 70 < θ_knee < 110 
              and 60 < θ_trunk < 120 and hip_y + 10 < knee_y
        """
        config = self.config['actions']['坐']
        
        # 高度范围检查
        height_ok = (config['geometry']['height_ratio_min'] < geo_features.height_normalized < 
                    config['geometry']['height_ratio_max'] and
                    config['geometry']['height_pixel_min'] < geo_features.height_pixels < 
                    config['geometry']['height_pixel_max'])
        
        # 膝盖弯曲检查
        knee_ok = (config['geometry']['knee_angle_min'] < geo_features.knee_angles[0] < 
                  config['geometry']['knee_angle_max'] and
                  config['geometry']['knee_angle_min'] < geo_features.knee_angles[1] < 
                  config['geometry']['knee_angle_max'])
        
        # 躯干角度检查
        trunk_ok = (config['geometry']['trunk_angle_min'] < geo_features.trunk_angle < 
                   config['geometry']['trunk_angle_max'])
        
        # 臀膝关系检查 (臀部高于膝盖)
        hip_knee_ok = geo_features.hip_knee_offset > config['geometry']['hip_knee_offset_min']
        
        # 计算置信度
        confidence = 0.0
        if height_ok: confidence += 0.3
        if knee_ok: confidence += 0.4
        if trunk_ok: confidence += 0.2
        if hip_knee_ok: confidence += 0.1
        
        is_sit = height_ok and knee_ok and trunk_ok and hip_knee_ok
        
        return is_sit, confidence
    
    def recognize_action_lie(self, geo_features: GeometricFeatures, 
                           dyn_features: DynamicFeatures) -> Tuple[bool, float]:
        """
        躺下动作识别
        条件: H_norm < 0.3 and θ_trunk < 30 and std(all_y) < 20 
              and movement_speed < 2 and consecutive_frames > 30
        """
        config = self.config['actions']['躺下']
        
        # 低高度检查
        height_ok = (geo_features.height_normalized < config['geometry']['height_ratio_max'] and
                    geo_features.height_pixels < config['geometry']['height_pixel_max'])
        
        # 水平躯干检查
        trunk_ok = geo_features.trunk_angle < config['geometry']['trunk_angle_max']
        
        # Y坐标方差检查 (身体展开)
        variance_ok = geo_features.y_variance < config['geometry']['y_variance_max']
        
        # 静止性检查
        stillness_ok = dyn_features.movement_speed < config['dynamics']['movement_speed_max']
        
        # 计算置信度
        confidence = 0.0
        if height_ok: confidence += 0.3
        if trunk_ok: confidence += 0.3
        if variance_ok: confidence += 0.2
        if stillness_ok: confidence += 0.2
        
        is_lie = height_ok and trunk_ok and variance_ok and stillness_ok
        
        return is_lie, confidence
    
    def recognize_action_drowsy(self, geo_features: GeometricFeatures, 
                              dyn_features: DynamicFeatures,
                              is_stand: bool, is_sit: bool) -> Tuple[bool, float]:
        """
        打瞌睡动作识别
        条件: (is_stand or is_sit) and head_drop > 40 
              and θ_neck < 45 and nod_count >= 2
        """
        config = self.config['actions']['打瞌睡']
        
        # 基线姿态检查
        baseline_ok = (config['baseline']['allow_stand'] and is_stand) or \
                     (config['baseline']['allow_sit'] and is_sit)
        
        # 头部下垂检查
        head_drop_ok = geo_features.head_drop > config['geometry']['head_drop_min']
        
        # 颈部前倾检查
        neck_ok = geo_features.neck_angle < config['geometry']['neck_angle_max']
        
        # 点头检测
        nod_ok = dyn_features.nod_count >= config['dynamics']['nod_count_min']
        
        # 头部移动幅度检查
        amplitude_ok = dyn_features.head_movement_amplitude > config['dynamics']['head_movement_amplitude_min']
        
        # 计算置信度
        confidence = 0.0
        if baseline_ok: confidence += 0.2
        if head_drop_ok: confidence += 0.3
        if neck_ok: confidence += 0.2
        if nod_ok: confidence += 0.2
        if amplitude_ok: confidence += 0.1
        
        is_drowsy = baseline_ok and head_drop_ok and neck_ok and (nod_ok or amplitude_ok)
        
        return is_drowsy, confidence
    
    def recognize_actions_single_person(self, keypoints: np.ndarray, 
                                      person_id: int = 0) -> Dict[str, float]:
        """单人动作识别主函数"""
        try:
            # 获取或创建人员状态
            if person_id not in self.person_states:
                self.person_states[person_id] = PersonState(person_id=person_id)
            
            person_state = self.person_states[person_id]
            
            # 提取几何特征
            geo_features = self.extract_geometric_features(keypoints)
            
            # 分析动态特征
            dyn_features = self.analyze_dynamic_features(person_state, geo_features)
            
            # 执行各动作识别
            is_stand, conf_stand = self.recognize_action_stand(geo_features, dyn_features)
            is_sit, conf_sit = self.recognize_action_sit(geo_features, dyn_features)
            is_lie, conf_lie = self.recognize_action_lie(geo_features, dyn_features)
            is_drowsy, conf_drowsy = self.recognize_action_drowsy(geo_features, dyn_features, is_stand, is_sit)
            
            # 构建结果
            results = {
                'stand': conf_stand if is_stand else 0.0,
                'sit': conf_sit if is_sit else 0.0,
                'lie': conf_lie if is_lie else 0.0,
                'drowsy': conf_drowsy if is_drowsy else 0.0
            }
            
            # 确定主要动作
            primary_action = max(results.items(), key=lambda x: x[1])
            
            # 更新连续帧计数
            if primary_action[1] > 0.5:  # 置信度阈值
                if person_state.last_action == primary_action[0]:
                    person_state.action_counters[primary_action[0]] = \
                        person_state.action_counters.get(primary_action[0], 0) + 1
                else:
                    person_state.action_counters = {primary_action[0]: 1}
                    person_state.last_action = primary_action[0]
            
            # 检查连续帧阈值
            action_confirmed = False
            for action, rules in self.config['actions'].items():
                action_eng = {'站立': 'stand', '坐': 'sit', '躺下': 'lie', '打瞌睡': 'drowsy'}[action]
                if action_eng == primary_action[0]:
                    min_frames = rules['dynamics'].get('min_consecutive_frames', 15)
                    if person_state.action_counters.get(action_eng, 0) >= min_frames:
                        action_confirmed = True
                        break
            
            # 发送观察者通知
            if action_confirmed and primary_action[1] > 0.7:
                self.notify_observers({
                    'person_id': person_id,
                    'action': primary_action[0],
                    'confidence': primary_action[1],
                    'consecutive_frames': person_state.action_counters.get(primary_action[0], 0),
                    'geometric_features': geo_features,
                    'dynamic_features': dyn_features
                })
            
            return results
            
        except Exception as e:
            logger.error(f"动作识别失败: {e}")
            return {'stand': 0.0, 'sit': 0.0, 'lie': 0.0, 'drowsy': 0.0}
    
    def recognize_actions_multiple_persons(self, all_keypoints: List[np.ndarray]) -> Dict[int, Dict[str, float]]:
        """多人动作识别"""
        results = {}
        
        for person_id, keypoints in enumerate(all_keypoints):
            if len(keypoints) > 0:
                results[person_id] = self.recognize_actions_single_person(keypoints, person_id)
            
        return results

# 观察者接口
class ActionObserver(ABC):
    """动作观察者抽象基类"""
    
    @abstractmethod
    def on_action_detected(self, event_data: dict):
        """动作检测回调"""
        pass

class ConsoleActionLogger(ActionObserver):
    """控制台动作记录器"""
    
    def on_action_detected(self, event_data: dict):
        """记录动作到控制台"""
        action_names = {
            'stand': '站立',
            'sit': '坐着', 
            'lie': '躺下',
            'drowsy': '打瞌睡'
        }
        
        action_cn = action_names.get(event_data['action'], event_data['action'])
        print(f"[动作检测] 人员{event_data['person_id']}: {action_cn} "
              f"(置信度: {event_data['confidence']:.2f}, "
              f"连续帧: {event_data['consecutive_frames']})")

class FileActionLogger(ActionObserver):
    """文件动作记录器"""
    
    def __init__(self, filename: str = 'action_log.txt'):
        self.filename = filename
    
    def on_action_detected(self, event_data: dict):
        """记录动作到文件"""
        import datetime
        
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        action_names = {
            'stand': '站立',
            'sit': '坐着',
            'lie': '躺下', 
            'drowsy': '打瞌睡'
        }
        
        action_cn = action_names.get(event_data['action'], event_data['action'])
        
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - 人员{event_data['person_id']}: {action_cn} "
                   f"(置信度: {event_data['confidence']:.2f})\n")

# 兼容性接口 - 保持向下兼容
def create_recognizer(config_path: str = 'rule_config.yaml') -> AdvancedActionRecognizer:
    """创建识别器实例"""
    return AdvancedActionRecognizer(config_path)

# 主函数测试
if __name__ == "__main__":
    # 创建识别器
    recognizer = AdvancedActionRecognizer()
    
    # 添加观察者
    recognizer.add_observer(ConsoleActionLogger())
    recognizer.add_observer(FileActionLogger('advanced_action_log.txt'))
    
    # 模拟测试数据
    test_keypoints = np.random.rand(17, 3) * 200  # 17个关键点，每个3维(x,y,conf)
    test_keypoints[:, 2] = 0.8  # 设置置信度
    
    # 测试识别
    results = recognizer.recognize_actions_single_person(test_keypoints)
    print(f"识别结果: {results}")
    
    logger.info("高精度动作识别系统测试完成")
