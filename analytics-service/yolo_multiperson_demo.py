#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于YOLOv8 Pose的多人实时姿态动作识别系统
使用ultralytics YOLOv8进行更准确的多人关键点检测
"""

import cv2
import numpy as np
import time
import yaml
from collections import deque, defaultdict
from ultralytics import YOLO
import torch
from behavior_model import AdvancedActionRecognizer, ConsoleActionLogger, FileActionLogger
import math
from typing import List, Dict, Tuple, Optional


class YOLOMultiPersonRecognizer:
    """基于YOLOv8的多人姿态识别器"""
    
    def __init__(self, config_path: str = 'rule_config.yaml', model_path: str = 'yolov8n-pose.pt'):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 初始化动作识别器
        self.action_recognizer = AdvancedActionRecognizer()
        
        # 初始化YOLOv8 Pose模型
        print(f"🤖 加载YOLOv8 Pose模型: {model_path}")
        self.yolo_model = YOLO(model_path)
        
        # 检查GPU可用性
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🔧 使用设备: {self.device}")
        
        # 模型参数
        self.conf_threshold = 0.5  # 置信度阈值
        self.iou_threshold = 0.7   # NMS阈值
        
        # 性能统计
        self.fps_history = deque(maxlen=30)
        self.frame_count = 0
        self.start_time = time.time()
        
        # 状态管理
        self.is_running = False
        self.tracked_persons = {}  # 跟踪的人员
        self.person_id_counter = 0
        
        # 动作映射（解决中文乱码）
        self.action_mapping = {
            "站立": "Standing",
            "坐": "Sitting", 
            "躺下": "Lying",
            "打瞌睡": "Dozing",
            "未知": "Unknown"
        }
        
        # 颜色定义（更多颜色）
        self.colors = [
            (0, 255, 0),    # 绿色
            (255, 0, 0),    # 蓝色
            (0, 0, 255),    # 红色
            (255, 255, 0),  # 青色
            (255, 0, 255),  # 洋红
            (0, 255, 255),  # 黄色
            (128, 255, 128), # 浅绿
            (255, 165, 0),  # 橙色
            (128, 0, 128),  # 紫色
            (255, 192, 203), # 粉色
        ]
        
        # 人员跟踪参数
        self.tracking_threshold = 150  # 像素距离阈值
        self.max_missing_frames = 15   # 最大丢失帧数
        
        # COCO姿态关键点定义（YOLOv8使用COCO格式）
        self.coco_keypoint_names = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # 骨架连接定义
        self.skeleton_connections = [
            (0, 1), (0, 2), (1, 3), (2, 4),  # 头部
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # 上身
            (5, 11), (6, 12), (11, 12),  # 躯干
            (11, 13), (13, 15), (12, 14), (14, 16)  # 下身
        ]
    
    def _yolo_to_coco_keypoints(self, yolo_keypoints: np.ndarray) -> List[float]:
        """
        将YOLOv8关键点转换为COCO格式
        YOLOv8输出格式: [x1, y1, conf1, x2, y2, conf2, ...]  (17个关键点)
        COCO格式: [x1, y1, conf1, x2, y2, conf2, ...]  (17个关键点 × 3 = 51个值)
        """
        if yolo_keypoints is None or len(yolo_keypoints) == 0:
            return [0.0] * 51
        
        # YOLOv8 pose输出的关键点已经是COCO格式，只需确保长度正确
        keypoints = yolo_keypoints.flatten().tolist()
        
        # 确保有51个值（17个关键点 × 3）
        if len(keypoints) < 51:
            keypoints.extend([0.0] * (51 - len(keypoints)))
        elif len(keypoints) > 51:
            keypoints = keypoints[:51]
        
        return keypoints
    
    def _get_person_center(self, keypoints: np.ndarray) -> Optional[Tuple[float, float]]:
        """获取人员中心点（基于肩膀和髋部）"""
        if keypoints is None or len(keypoints) < 51:
            return None
        
        # 重塑为 (17, 3) 形状
        kpts = keypoints.reshape(17, 3)
        
        # 使用肩膀和髋部计算中心点
        key_points = []
        
        # 左右肩膀 (索引5, 6)
        if kpts[5, 2] > 0.3:  # 左肩置信度
            key_points.append((kpts[5, 0], kpts[5, 1]))
        if kpts[6, 2] > 0.3:  # 右肩置信度
            key_points.append((kpts[6, 0], kpts[6, 1]))
        
        # 左右髋部 (索引11, 12)
        if kpts[11, 2] > 0.3:  # 左髋置信度
            key_points.append((kpts[11, 0], kpts[11, 1]))
        if kpts[12, 2] > 0.3:  # 右髋置信度
            key_points.append((kpts[12, 0], kpts[12, 1]))
        
        if key_points:
            center_x = sum(p[0] for p in key_points) / len(key_points)
            center_y = sum(p[1] for p in key_points) / len(key_points)
            return (center_x, center_y)
        
        return None
    
    def _calculate_distance(self, point1: Optional[Tuple[float, float]], 
                          point2: Optional[Tuple[float, float]]) -> float:
        """计算两点距离"""
        if point1 is None or point2 is None:
            return float('inf')
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def _track_persons(self, detections: List[Dict]) -> List[int]:
        """人员跟踪算法"""
        current_frame_persons = []
        
        # 为每个检测分配ID
        for detection in detections:
            keypoints = detection['keypoints']
            center = self._get_person_center(keypoints)
            
            if center is None:
                continue
            
            # 寻找最近的已跟踪人员
            best_match_id = None
            min_distance = float('inf')
            
            for person_id, person_data in self.tracked_persons.items():
                if person_data.get('missing_frames', 0) < self.max_missing_frames:
                    last_center = person_data.get('last_center')
                    distance = self._calculate_distance(center, last_center)
                    
                    if distance < min_distance and distance < self.tracking_threshold:
                        min_distance = distance
                        best_match_id = person_id
            
            # 分配ID
            if best_match_id is not None:
                # 更新已存在的人员
                person_id = best_match_id
                self.tracked_persons[person_id]['missing_frames'] = 0
            else:
                # 创建新人员
                person_id = self.person_id_counter
                self.person_id_counter += 1
                self.tracked_persons[person_id] = {'missing_frames': 0}
            
            # 更新人员信息
            self.tracked_persons[person_id].update({
                'keypoints': keypoints,
                'last_center': center,
                'bbox': detection.get('bbox'),
                'confidence': detection.get('confidence', 0.0),
                'last_seen_frame': self.frame_count
            })
            
            current_frame_persons.append(person_id)
        
        # 增加未检测到的人员的丢失帧数
        for person_id in list(self.tracked_persons.keys()):
            if person_id not in current_frame_persons:
                self.tracked_persons[person_id]['missing_frames'] += 1
                
                # 删除丢失太久的人员
                if self.tracked_persons[person_id]['missing_frames'] > self.max_missing_frames:
                    del self.tracked_persons[person_id]
        
        return current_frame_persons
    
    def _draw_skeleton(self, image: np.ndarray, keypoints: np.ndarray, color: Tuple[int, int, int]):
        """绘制人体骨架"""
        if keypoints is None or len(keypoints) < 51:
            return image
        
        # 重塑为 (17, 3) 形状
        kpts = keypoints.reshape(17, 3)
        
        # 绘制关键点
        for i, (x, y, conf) in enumerate(kpts):
            if conf > 0.3:  # 置信度阈值
                cv2.circle(image, (int(x), int(y)), 3, color, -1)
                # 可选：显示关键点编号
                # cv2.putText(image, str(i), (int(x), int(y-10)), 
                #            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
        
        # 绘制骨架连接
        for start_idx, end_idx in self.skeleton_connections:
            if (kpts[start_idx, 2] > 0.3 and kpts[end_idx, 2] > 0.3):
                start_point = (int(kpts[start_idx, 0]), int(kpts[start_idx, 1]))
                end_point = (int(kpts[end_idx, 0]), int(kpts[end_idx, 1]))
                cv2.line(image, start_point, end_point, color, 2)
        
        return image
    
    def _draw_person_info(self, image: np.ndarray, person_id: int, person_data: Dict, 
                         action: str, confidence: float):
        """绘制单个人员信息"""
        keypoints = person_data.get('keypoints')
        center = person_data.get('last_center')
        bbox = person_data.get('bbox')
        detection_conf = person_data.get('confidence', 0.0)
        
        if keypoints is not None and center is not None:
            color = self.colors[person_id % len(self.colors)]
            
            # 绘制人体骨架
            image = self._draw_skeleton(image, keypoints, color)
            
            # 绘制边界框（如果有）
            if bbox is not None:
                x1, y1, x2, y2 = map(int, bbox)
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 在人员中心绘制ID和动作信息
            center_x, center_y = int(center[0]), int(center[1])
            
            # 人员ID背景
            id_text = f"P{person_id+1}"
            text_size = cv2.getTextSize(id_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(image, 
                         (center_x - text_size[0]//2 - 10, center_y - 50),
                         (center_x + text_size[0]//2 + 10, center_y - 20),
                         (0, 0, 0), -1)
            cv2.rectangle(image, 
                         (center_x - text_size[0]//2 - 10, center_y - 50),
                         (center_x + text_size[0]//2 + 10, center_y - 20),
                         color, 2)
            
            # 人员ID
            cv2.putText(image, id_text, 
                       (center_x - text_size[0]//2, center_y - 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            # 动作信息
            english_action = self.action_mapping.get(action, action)
            action_text = f"{english_action[:8]}"  # 限制长度
            
            # 动作背景
            action_size = cv2.getTextSize(action_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(image,
                         (center_x - action_size[0]//2 - 5, center_y + 10),
                         (center_x + action_size[0]//2 + 5, center_y + 35),
                         (0, 0, 0), -1)
            cv2.rectangle(image,
                         (center_x - action_size[0]//2 - 5, center_y + 10),
                         (center_x + action_size[0]//2 + 5, center_y + 35),
                         color, 1)
            
            cv2.putText(image, action_text,
                       (center_x - action_size[0]//2, center_y + 28),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # 置信度信息
            conf_text = f"{confidence:.2f}"
            cv2.putText(image, conf_text,
                       (center_x - 20, center_y + 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    def _draw_info_panel(self, image: np.ndarray):
        """绘制总体信息面板"""
        h, w = image.shape[:2]
        
        # 主信息面板
        panel_height = 140 + len(self.tracked_persons) * 25
        cv2.rectangle(image, (10, 10), (600, panel_height), (0, 0, 0), -1)
        cv2.rectangle(image, (10, 10), (600, panel_height), (255, 255, 255), 2)
        
        # 标题
        cv2.putText(image, "YOLOv8 Multi-Person Action Recognition", 
                   (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        
        # FPS
        current_fps = len(self.fps_history) / sum(self.fps_history) if self.fps_history else 0
        cv2.putText(image, f"FPS: {current_fps:.1f}", 
                   (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 设备信息
        cv2.putText(image, f"Device: {self.device.upper()}", 
                   (120, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 活跃人数
        active_count = len([p for p in self.tracked_persons.values() if p.get('missing_frames', 0) < 3])
        cv2.putText(image, f"Active: {active_count}", 
                   (220, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 总跟踪人数
        cv2.putText(image, f"Total: {len(self.tracked_persons)}", 
                   (300, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 时间戳
        current_time = time.strftime("%H:%M:%S", time.localtime())
        cv2.putText(image, current_time, 
                   (400, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 帧计数
        cv2.putText(image, f"Frame: {self.frame_count}", 
                   (500, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 模型信息
        cv2.putText(image, f"Conf: {self.conf_threshold} | IoU: {self.iou_threshold}", 
                   (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)
        
        # 状态
        status = f"TRACKING {active_count} PERSONS" if active_count > 0 else "SCANNING..."
        cv2.putText(image, status, 
                   (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return image
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """处理帧（YOLOv8多人检测）"""
        frame_start = time.time()
        
        h, w = frame.shape[:2]
        
        # YOLOv8姿态检测
        results = self.yolo_model(frame, conf=self.conf_threshold, iou=self.iou_threshold, verbose=False)
        
        # 解析检测结果
        detections = []
        
        for result in results:
            if result.keypoints is not None:
                boxes = result.boxes
                keypoints = result.keypoints
                
                for i in range(len(keypoints.data)):
                    # 获取边界框
                    if boxes is not None and i < len(boxes.data):
                        bbox = boxes.data[i][:4].cpu().numpy()  # x1, y1, x2, y2
                        detection_conf = boxes.data[i][4].cpu().numpy()  # 检测置信度
                    else:
                        bbox = None
                        detection_conf = 0.0
                    
                    # 获取关键点 (17, 3) -> flatten to (51,)
                    kpts = keypoints.data[i].cpu().numpy()  # (17, 3)
                    
                    detections.append({
                        'keypoints': kpts.flatten(),  # 转换为一维数组
                        'bbox': bbox,
                        'confidence': detection_conf
                    })
        
        # 人员跟踪
        active_persons = self._track_persons(detections)
        
        # 动作识别和绘制
        for person_id in active_persons:
            person_data = self.tracked_persons[person_id]
            keypoints = person_data.get('keypoints')
            
            if keypoints is not None:
                # 转换为COCO格式（已经是了，只需确保长度）
                coco_keypoints = self._yolo_to_coco_keypoints(keypoints)
                
                # 动作识别
                # 将关键点转换为numpy数组格式 (17, 3)
                keypoints_array = np.array(coco_keypoints).reshape(17, 3)
                recognition_results = self.action_recognizer.recognize_actions_single_person(keypoints_array, person_id)
                
                # 获取最高置信度的动作
                if recognition_results:
                    action_item = max(recognition_results.items(), key=lambda x: x[1])
                    action_eng = action_item[0]
                    confidence = action_item[1]
                    
                    # 转换为中文动作名
                    action_cn_map = {'stand': '站立', 'sit': '坐', 'lie': '躺下', 'drowsy': '打瞌睡'}
                    action = action_cn_map.get(action_eng, '未知')
                else:
                    action = '未知'
                    confidence = 0.0
                
                # 绘制人员信息
                self._draw_person_info(frame, person_id, person_data, action, confidence)
                
                # 调试输出
                english_action = self.action_mapping.get(action, action)
                print(f"Person {person_id+1}: {english_action} (置信度: {confidence:.3f}) "
                      f"[检测置信度: {person_data.get('confidence', 0.0):.3f}]")
        
        # 绘制信息面板
        frame = self._draw_info_panel(frame)
        
        # 更新性能统计
        frame_time = time.time() - frame_start
        self.fps_history.append(frame_time)
        self.frame_count += 1
        
        return frame
    
    def run_video(self, source):
        """运行视频处理（支持摄像头ID、视频文件、RTSP流）"""
        if isinstance(source, int):
            print(f"🎥 启动摄像头 {source} (YOLOv8多人模式)...")
        else:
            print(f"🎥 处理视频: {source} (YOLOv8多人模式)...")
        
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频源: {source}")
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"📋 视频信息: {width}x{height}, {fps:.1f}FPS, {total_frames} frames")
        
        self.is_running = True
        print("📸 开始YOLOv8多人跟踪...")
        print("🎮 控制: 'q'退出, 's'截图, 'r'重置跟踪, 'c'清除历史, '='提高置信度, '-'降低置信度")
        
        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    if isinstance(source, str) and source.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                        print("📹 视频播放完毕")
                        break
                    else:
                        print("❌ 无法读取帧")
                        break
                
                # 处理帧
                processed_frame = self.process_frame(frame)
                
                # 显示
                cv2.imshow("YOLOv8 Multi-Person Action Recognition", processed_frame)
                
                # 键盘控制
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    # 截图
                    timestamp = int(time.time())
                    filename = f"yolo_multiperson_{timestamp}.jpg"
                    cv2.imwrite(filename, processed_frame)
                    print(f"📷 截图保存: {filename}")
                elif key == ord('r'):
                    # 重置跟踪
                    self.tracked_persons.clear()
                    self.person_id_counter = 0
                    print("🔄 人员跟踪已重置")
                elif key == ord('c'):
                    # 清除历史
                    self.fps_history.clear()
                    self.frame_count = 0
                    self.start_time = time.time()
                    print("🗑️ 历史数据已清除")
                elif key == ord('=') or key == ord('+'):
                    # 提高置信度
                    self.conf_threshold = min(0.9, self.conf_threshold + 0.05)
                    print(f"📈 置信度阈值: {self.conf_threshold:.2f}")
                elif key == ord('-'):
                    # 降低置信度
                    self.conf_threshold = max(0.1, self.conf_threshold - 0.05)
                    print(f"📉 置信度阈值: {self.conf_threshold:.2f}")
        
        finally:
            self.is_running = False
            cap.release()
            cv2.destroyAllWindows()
            print("📊 YOLOv8识别统计:")
            print(f"   总帧数: {self.frame_count}")
            print(f"   运行时间: {time.time() - self.start_time:.2f}s")
            print(f"   跟踪过的人数: {self.person_id_counter}")
            if self.frame_count > 0:
                avg_fps = self.frame_count / (time.time() - self.start_time)
                print(f"   平均FPS: {avg_fps:.2f}")


def main():
    """主函数"""
    print("🤖 YOLOv8多人姿态动作识别系统")
    print("✅ 更准确的多人检测") 
    print("✅ 原生COCO关键点格式")
    print("✅ GPU加速支持")
    print("=" * 50)
    
    # 可选择不同的YOLOv8模型
    # yolov8n-pose.pt (最快)
    # yolov8s-pose.pt (平衡)  
    # yolov8m-pose.pt (更准确)
    # yolov8l-pose.pt (最准确)
    
    recognizer = YOLOMultiPersonRecognizer(model_path='yolo11l-pose.pt')
    
    try:
        # 可以使用摄像头、视频文件或RTSP流
        # recognizer.run_video(0)  # 摄像头
        recognizer.run_video("11.mp4")  # 视频文件
        # recognizer.run_video("rtsp://...")  # RTSP流
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🏁 YOLOv8识别程序结束")


if __name__ == '__main__':
    main() 