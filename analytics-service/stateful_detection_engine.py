#!/usr/bin/env python3
"""
有状态的事件检测引擎
支持基于多帧时序分析的事件检测
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import deque, defaultdict
import numpy as np
import threading
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """会话状态"""
    session_id: str
    scene: str
    created_at: datetime
    last_update: datetime
    frame_buffer: deque  # 帧缓冲区
    event_states: Dict[str, Dict]  # 各事件的状态
    triggered_events: List[Dict]  # 已触发的事件
    
    
class StatefulDetectionEngine:
    """有状态的检测引擎"""
    
    def __init__(self, config_path: str = 'event_rules_config_no_zones.json'):
        """初始化引擎"""
        self.config = self._load_config(config_path)
        self.sessions = {}  # session_id -> SessionState
        self.lock = threading.Lock()
        
        # 启动清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_sessions, daemon=True)
        self.cleanup_thread.start()
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    def create_session(self, session_id: str, scene: str) -> None:
        """创建新会话"""
        with self.lock:
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                scene=scene,
                created_at=datetime.now(),
                last_update=datetime.now(),
                frame_buffer=deque(maxlen=1000),  # 最多保存1000帧
                event_states=defaultdict(dict),
                triggered_events=[]
            )
            logger.info(f"创建会话: {session_id}")
            
    def process_frame(self, session_id: str, frame_data: Dict) -> List[Dict]:
        """处理单帧数据，返回新触发的事件"""
        with self.lock:
            if session_id not in self.sessions:
                self.create_session(session_id, frame_data.get('scene', '未知'))
                
            session = self.sessions[session_id]
            session.last_update = datetime.now()
            
            # 添加到帧缓冲
            session.frame_buffer.append(frame_data)
            
            # 检测各类事件
            new_events = []
            
            for event_name, rule in self.config['event_rules'].items():
                if not rule.get('enabled', True):
                    continue
                    
                # 根据事件类型调用不同的检测方法
                event = None
                
                if event_name == "异常物品检测":
                    event = self._check_prohibited_items(session, event_name, rule)
                elif event_name == "人员睡岗":
                    event = self._check_sleep_posture(session, event_name, rule)
                elif event_name == "违规使用手机":
                    event = self._check_phone_usage(session, event_name, rule)
                elif event_name == "抽烟行为":
                    event = self._check_smoking(session, event_name, rule)
                elif event_name == "人员跌倒":
                    event = self._check_fall(session, event_name, rule)
                elif event_name == "单人看护" or event_name == "单人谈话":
                    event = self._check_single_person_care(session, event_name, rule)
                elif event_name == "人员攀高":
                    event = self._check_climbing(session, event_name, rule)
                    
                if event:
                    new_events.append(event)
                    session.triggered_events.append(event)
                    
            return new_events
            
    def _check_prohibited_items(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测异常物品（需要连续10帧中≥8帧）"""
        params = rule['detection_params']
        prohibited_list = rule.get('prohibited_items_list', [])
        
        # 获取最近的帧
        recent_frames = list(session.frame_buffer)[-params['tracking_frames']:]
        if len(recent_frames) < params['tracking_frames']:
            return None
            
        # 统计每个物品的出现次数
        item_counts = defaultdict(int)
        
        for frame in recent_frames:
            yolo_results = frame.get('yolo_results', [])
            for obj in yolo_results:
                if obj.get('class_name') in prohibited_list:
                    item_counts[obj['class_name']] += 1
                    
        # 检查是否有物品满足条件
        for item, count in item_counts.items():
            if count >= params['min_valid_frames']:
                # 检查是否已经触发过
                state_key = f"{event_name}_{item}"
                if state_key not in session.event_states:
                    session.event_states[state_key] = {
                        'triggered_at': datetime.now(),
                        'item': item,
                        'count': count
                    }
                    
                    return {
                        'event_name': event_name,
                        'event_type': rule['category'],
                        'timestamp': datetime.now().isoformat(),
                        'confidence': 0.9,
                        'details': {
                            'detected_object': item,
                            'tracking_frames': params['tracking_frames'],
                            'valid_frames': count
                        }
                    }
                    
        return None
        
    def _check_phone_usage(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测手机使用（5分钟内≥90%帧检测到）"""
        params = rule['detection_params']
        target_objects = rule['detection_objects']
        
        # 获取5分钟内的帧
        analysis_window = params['analysis_window']  # 300秒
        current_time = datetime.now()
        recent_frames = []
        
        for frame in reversed(session.frame_buffer):
            frame_time = datetime.fromisoformat(frame['timestamp'])
            if (current_time - frame_time).total_seconds() <= analysis_window:
                recent_frames.append(frame)
            else:
                break
                
        if not recent_frames:
            return None
            
        # 统计检测到手机的帧数
        phone_frames = 0
        for frame in recent_frames:
            yolo_results = frame.get('yolo_results', [])
            if any(obj.get('class_name') in target_objects for obj in yolo_results):
                phone_frames += 1
                
        detection_ratio = phone_frames / len(recent_frames)
        
        if detection_ratio >= params['min_detection_ratio']:
            # 检查是否在冷却期
            state_key = event_name
            last_trigger = session.event_states.get(state_key, {}).get('last_trigger')
            
            if last_trigger:
                if (current_time - last_trigger).total_seconds() < 300:  # 5分钟冷却
                    return None
                    
            session.event_states[state_key] = {'last_trigger': current_time}
            
            return {
                'event_name': event_name,
                'event_type': rule['category'],
                'timestamp': current_time.isoformat(),
                'confidence': detection_ratio,
                'details': {
                    'detection_ratio': detection_ratio,
                    'analysis_duration': len(recent_frames) * 2  # 假设2秒/帧
                }
            }
            
        return None
        
    def _check_sleep_posture(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测睡岗（5分钟内≥70%为睡姿）"""
        params = rule['detection_params']
        
        # 获取5分钟内的帧
        analysis_window = params['analysis_window']
        current_time = datetime.now()
        recent_frames = []
        
        for frame in reversed(session.frame_buffer):
            frame_time = datetime.fromisoformat(frame['timestamp'])
            if (current_time - frame_time).total_seconds() <= analysis_window:
                recent_frames.append(frame)
            else:
                break
                
        if not recent_frames:
            return None
            
        # 统计睡姿帧数
        sleep_frames = 0
        for frame in recent_frames:
            pose_results = frame.get('pose_results', [])
            for pose in pose_results:
                if self._is_sleeping_posture(pose):
                    sleep_frames += 1
                    break
                    
        sleep_ratio = sleep_frames / len(recent_frames)
        
        if sleep_ratio >= params['min_sleep_ratio']:
            state_key = event_name
            last_trigger = session.event_states.get(state_key, {}).get('last_trigger')
            
            if last_trigger:
                if (current_time - last_trigger).total_seconds() < 300:
                    return None
                    
            session.event_states[state_key] = {'last_trigger': current_time}
            
            return {
                'event_name': event_name,
                'event_type': rule['category'],
                'timestamp': current_time.isoformat(),
                'confidence': sleep_ratio,
                'duration': analysis_window * sleep_ratio,
                'details': {
                    'sleep_ratio': sleep_ratio,
                    'analysis_frames': len(recent_frames)
                }
            }
            
        return None
        
    def _check_fall(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测跌倒（2分钟内≥70%为跌倒状态）"""
        params = rule['detection_params']
        
        # 获取2分钟内的帧
        analysis_window = params['analysis_window']  # 120秒
        current_time = datetime.now()
        recent_frames = []
        
        for frame in reversed(session.frame_buffer):
            frame_time = datetime.fromisoformat(frame['timestamp'])
            if (current_time - frame_time).total_seconds() <= analysis_window:
                recent_frames.append(frame)
            else:
                break
                
        if not recent_frames:
            return None
            
        # 统计跌倒帧数
        fall_frames = 0
        for frame in recent_frames:
            pose_results = frame.get('pose_results', [])
            for pose in pose_results:
                if self._is_fallen_posture(pose):
                    fall_frames += 1
                    break
                    
        fall_ratio = fall_frames / len(recent_frames)
        
        if fall_ratio >= params['min_fall_ratio']:
            state_key = event_name
            if state_key not in session.event_states:
                session.event_states[state_key] = {'triggered_at': current_time}
                
                return {
                    'event_name': event_name,
                    'event_type': rule['category'],
                    'timestamp': current_time.isoformat(),
                    'confidence': fall_ratio,
                    'duration': analysis_window * fall_ratio,
                    'details': {
                        'fall_ratio': fall_ratio,
                        'location': recent_frames[-1].get('metadata', {}).get('current_zone', 'unknown')
                    }
                }
                
        return None
        
    def _check_smoking(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测抽烟（5分钟内≥90%检测到吸烟物品）"""
        return self._check_phone_usage(session, event_name, rule)  # 逻辑相同
        
    def _check_single_person_care(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测单人看护/谈话（60帧中≥90%为特定姿态）"""
        params = rule['detection_params']
        detection_rules = rule['detection_rules']
        
        # 获取最近60帧
        total_frames = params['total_frames']
        recent_frames = list(session.frame_buffer)[-total_frames:]
        
        if len(recent_frames) < total_frames:
            return None
            
        # 检查人数和姿态
        target_posture = detection_rules['caregiver_posture']
        valid_frames = 0
        
        for frame in recent_frames:
            yolo_results = frame.get('yolo_results', [])
            pose_results = frame.get('pose_results', [])
            
            # 检查是否有2个人
            persons = [obj for obj in yolo_results if obj.get('class_name') == 'person']
            if len(persons) == 2 and pose_results:
                # 简化：假设第一个是看护人员
                if self._check_posture_type(pose_results[0], target_posture):
                    valid_frames += 1
                    
        ratio = valid_frames / total_frames
        min_ratio = params.get('min_standing_ratio', params.get('min_sitting_ratio', 0.9))
        
        if ratio >= min_ratio:
            state_key = event_name
            last_trigger = session.event_states.get(state_key, {}).get('last_trigger')
            current_time = datetime.now()
            
            if last_trigger:
                if (current_time - last_trigger).total_seconds() < 180:  # 3分钟冷却
                    return None
                    
            session.event_states[state_key] = {'last_trigger': current_time}
            
            return {
                'event_name': event_name,
                'event_type': rule['category'],
                'timestamp': current_time.isoformat(),
                'confidence': ratio,
                'duration': params['analysis_duration'],
                'details': {
                    f'{target_posture}_ratio': ratio
                }
            }
            
        return None
        
    def _check_climbing(self, session: SessionState, event_name: str, rule: Dict) -> Optional[Dict]:
        """检测人员攀高（2分钟内≥70%站立且高度超过阈值）"""
        params = rule['detection_params']
        height_threshold = rule.get('detection_rules', {}).get('height_threshold', 1.5)
        
        # 获取2分钟内的帧
        analysis_window = params['analysis_window']
        current_time = datetime.now()
        recent_frames = []
        
        for frame in reversed(session.frame_buffer):
            frame_time = datetime.fromisoformat(frame['timestamp'])
            if (current_time - frame_time).total_seconds() <= analysis_window:
                recent_frames.append(frame)
            else:
                break
                
        if not recent_frames:
            return None
            
        # 统计站立且可能攀高的帧数
        climbing_frames = 0
        for frame in recent_frames:
            pose_results = frame.get('pose_results', [])
            yolo_results = frame.get('yolo_results', [])
            
            # 检查是否只有一个人且为站立姿态
            persons = [obj for obj in yolo_results if obj.get('class_name') == 'person']
            if len(persons) == 1 and pose_results:
                if self._check_posture_type(pose_results[0], 'standing'):
                    # 可以基于关键点位置判断高度
                    keypoints = pose_results[0].get('keypoints', {})
                    if self._is_elevated_position(keypoints, height_threshold):
                        climbing_frames += 1
                    
        climbing_ratio = climbing_frames / len(recent_frames)
        
        if climbing_ratio >= params['min_standing_ratio']:
            state_key = event_name
            
            if state_key not in session.event_states:
                session.event_states[state_key] = {'triggered_at': current_time}
                
                return {
                    'event_name': event_name,
                    'event_type': rule['category'],
                    'timestamp': current_time.isoformat(),
                    'confidence': climbing_ratio,
                    'details': {
                        'standing_ratio': climbing_ratio,
                        'height_threshold': height_threshold
                    }
                }
                
        return None
        
    # 辅助方法
    def _is_sleeping_posture(self, pose_data: Dict) -> bool:
        """判断是否为睡姿"""
        posture = pose_data.get('posture')
        if posture == 'sleeping':
            return True
            
        # 基于关键点判断
        keypoints = pose_data.get('keypoints', {})
        if 'nose' in keypoints and 'left_shoulder' in keypoints:
            head_y = keypoints['nose'].get('y', 0)
            shoulder_y = keypoints['left_shoulder'].get('y', 0)
            return head_y > shoulder_y + 30
            
        return False
        
    def _is_fallen_posture(self, pose_data: Dict) -> bool:
        """判断是否为跌倒姿态"""
        posture = pose_data.get('posture')
        if posture == 'fallen':
            return True
            
        # 基于关键点判断
        keypoints = pose_data.get('keypoints', {})
        if 'hip' in keypoints:
            hip_y = keypoints['hip'].get('y', 0)
            return hip_y > 350  # 阈值需要根据实际调整
            
        return False
        
    def _check_posture_type(self, pose_data: Dict, target_posture: str) -> bool:
        """检查姿态类型"""
        return pose_data.get('posture') == target_posture
        
    def _is_elevated_position(self, keypoints: Dict, height_threshold: float) -> bool:
        """判断是否处于高处位置"""
        # 基于脚部关键点的Y坐标判断
        # Y坐标越小表示越高（图像坐标系）
        foot_keypoints = ['left_ankle', 'right_ankle', 'left_foot', 'right_foot']
        
        min_y = float('inf')
        for kp_name in foot_keypoints:
            if kp_name in keypoints:
                y = keypoints[kp_name].get('y', float('inf'))
                min_y = min(min_y, y)
                
        # 假设正常地面位置的Y坐标约为400-500
        # 如果脚部Y坐标小于某个阈值，认为在高处
        ground_level = 400  # 需要根据实际相机设置调整
        height_pixels = ground_level - min_y
        
        # 简化判断：如果脚部位置明显高于地面
        return height_pixels > 100  # 像素阈值，需要根据实际调整
        
    def get_session_status(self, session_id: str) -> Dict:
        """获取会话状态"""
        with self.lock:
            if session_id not in self.sessions:
                return {'exists': False}
                
            session = self.sessions[session_id]
            return {
                'exists': True,
                'scene': session.scene,
                'created_at': session.created_at.isoformat(),
                'last_update': session.last_update.isoformat(),
                'frame_count': len(session.frame_buffer),
                'triggered_events': len(session.triggered_events),
                'active_states': list(session.event_states.keys())
            }
            
    def get_session_events(self, session_id: str) -> List[Dict]:
        """获取会话的所有触发事件"""
        with self.lock:
            if session_id not in self.sessions:
                return []
            return self.sessions[session_id].triggered_events.copy()
            
    def clear_session(self, session_id: str) -> bool:
        """清除会话"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"清除会话: {session_id}")
                return True
            return False
            
    def _cleanup_sessions(self):
        """定期清理过期会话"""
        while True:
            time.sleep(300)  # 每5分钟检查一次
            
            with self.lock:
                current_time = datetime.now()
                expired_sessions = []
                
                for session_id, session in self.sessions.items():
                    # 超过30分钟没有更新的会话
                    if (current_time - session.last_update).total_seconds() > 1800:
                        expired_sessions.append(session_id)
                        
                for session_id in expired_sessions:
                    del self.sessions[session_id]
                    logger.info(f"清理过期会话: {session_id}")
                    
                if expired_sessions:
                    logger.info(f"清理了 {len(expired_sessions)} 个过期会话") 