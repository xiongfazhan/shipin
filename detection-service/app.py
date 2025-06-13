#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测引擎服务 - Detection Service
负责YOLO模型推理和GPU资源管理
"""

import os
import sys
import time
import logging
import json
import threading
import queue
import base64
import requests
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify
import cv2
import numpy as np
import yaml
from importlib import import_module
import torch

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'processors'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'engines'))

from modules.yolo_detector import YOLODetector

# 多GPU处理功能已下线，保留占位符以兼容旧代码
MultiGPUProcessor = None
MULTI_GPU_AVAILABLE = False

class DetectionService:
    """检测引擎服务 - 专注于AI推理"""
    
    def __init__(self, config_file: str = 'config/detection_config.json'):
        self.config_file = config_file
        self.config = self._load_config()
        
        # 初始化日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Flask应用
        self.app = Flask(__name__)
        self._setup_routes()
        
        # 核心组件
        self.yolo_detector = None
        self.gpu_processor = None  # 已废弃，保持 None
        self.detection_queue = queue.Queue(maxsize=self.config.get('processing', {}).get('queue_size', 100))
        
        # 服务配置
        self.storage_service_url = self.config.get('services', {}).get('storage_service', '')
        # 1) 读取配置文件 → 2) 允许用环境变量覆盖 → 3) 回退默认值
        self.analytics_service_url = (
            os.environ.get('ANALYTICS_SERVICE_URL')                # 环境变量优先
            or self.config.get('services', {}).get('analytics_service', '')
            or 'http://localhost:8086'                             # 最后兜底
        ).rstrip('/')                                              # 去掉尾部 /

        # 打印到日志，启动时即可确认地址是否正确
        self.logger.info(f"分析服务 URL: {self.analytics_service_url}")
        
        # 统计信息
        self.stats = {
            'start_time': time.time(),
            'total_detections': 0,
            'successful_detections': 0,
            'failed_detections': 0,
            'average_inference_time': 0.0,
            'gpu_utilization': 0.0,
            'queue_size': 0
        }
        
        # -------- 先检测 algorithms.yml 是否已启用 object 引擎 --------
        self.object_engine_enabled = self._object_plugin_enabled()

        # 仅在未启用 object 引擎时才加载内置 YOLODetector，避免重复加载
        if not self.object_engine_enabled:
            self._initialize_models()

        # 加载插件引擎（可能包含 object 引擎）
        self._init_engines()
        
        # 启动处理线程
        self._start_processing_threads()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8082,
                'debug': False
            },
            'services': {
                'storage_service': 'http://localhost:8083',
                'analytics_service': 'http://localhost:8086'
            },
            'model': {
                'model_path': '/app/models/yolov8n.pt',
                'confidence_threshold': 0.5,
                'iou_threshold': 0.45,
                'device': 'auto',  # 'auto', 'cpu', 'cuda:0'
                'batch_size': 1
            },
            'gpu': {
                'enabled': True,
                'devices': [0, 1, 2, 3],
                'memory_fraction': 0.8,
                'allow_growth': True
            },
            'processing': {
                'max_workers': 4,
                'queue_size': 100,
                'batch_processing': True,
                'max_batch_size': 8,
                'batch_timeout': 0.1
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/detection.log'
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                        elif isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if sub_key not in config[key]:
                                    config[key][sub_key] = sub_value
                    return config
            except Exception as e:
                print(f"加载配置文件失败: {e}，使用默认配置")
        
        # 创建配置目录和文件
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        return default_config
    
    def _setup_logging(self):
        """设置日志系统"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('file', 'logs/detection.log')
        
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.handlers.clear()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    def _initialize_models(self):
        """初始化AI模型"""
        try:
            model_config = self.config.get('model', {})
            gpu_config = self.config.get('gpu', {})
            
            self.logger.info("初始化YOLO检测器...")
            self.yolo_detector = YOLODetector(
                model_path=model_config.get('model_path', 'models/yolov8n.pt'),
                confidence_threshold=model_config.get('confidence_threshold', 0.5),
                device=model_config.get('device', 'auto')
            )
            
            # 多GPUProcessor 功能已移除；始终使用单模型推理
            
            self.logger.info("AI模型初始化完成")
            
        except Exception as e:
            self.logger.error(f"模型初始化失败: {e}")
            # 使用CPU作为后备
            self.yolo_detector = YOLODetector(device='cpu')
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """健康检查"""
            return jsonify({
                'status': 'healthy',
                'service': 'detection',
                'timestamp': time.time(),
                'uptime': time.time() - self.stats['start_time'],
                'model_loaded': self.yolo_detector is not None,
                'gpu_available': False,
                'queue_size': self.stats['queue_size']
            })
        
        @self.app.route('/api/detect/frame', methods=['POST'])
        def detect_frame():
            """单帧检测"""
            try:
                data = request.get_json()
                
                # 验证请求数据
                if 'image' not in data:
                    return jsonify({'error': 'Missing image data'}), 400
                
                stream_id = data.get('stream_id', 'unknown')
                timestamp = data.get('timestamp', time.time())
                config = data.get('config', {})
                
                # 解码图像
                image_data = base64.b64decode(data['image'])
                nparr = np.frombuffer(image_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    return jsonify({'error': 'Invalid image data'}), 400
                
                # 执行检测
                results = self._process_single_frame(frame, stream_id, timestamp, config)
                
                # 异步发送结果
                for res in results:
                    self._send_results_async(res)
                
                # 向客户端返回简化信息（兼容旧字段，以首个object结果为准）
                primary = next((r for r in results if r.get('algo_type') == 'object'), results[0])

                return jsonify({
                    'status': 'success',
                    'stream_id': stream_id,
                    'object_count': primary.get('total_objects', 0),
                    'pose_persons': primary.get('total_persons', 0) if primary.get('algo_type') == 'pose' else 0,
                    'processing_time': primary.get('processing_time', 0)
                })
                
            except Exception as e:
                self.logger.error(f"单帧检测失败: {e}")
                self.stats['failed_detections'] += 1
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/detect/batch', methods=['POST'])
        def detect_batch():
            """批量检测"""
            try:
                data = request.get_json()
                
                if 'frames' not in data or not isinstance(data['frames'], list):
                    return jsonify({'error': 'Missing or invalid frames data'}), 400
                
                # 处理批量帧
                results = []
                for frame_data in data['frames']:
                    # 解码和处理每一帧
                    image_data = base64.b64decode(frame_data['image'])
                    nparr = np.frombuffer(image_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        result_list = self._process_single_frame(
                            frame,
                            frame_data.get('stream_id', 'unknown'),
                            frame_data.get('timestamp', time.time()),
                            frame_data.get('config', {})
                        )
                        results.extend(result_list)
                
                # 批量发送结果
                for result in results:
                    self._send_results_async(result)
                
                return jsonify({
                    'status': 'success',
                    'processed_count': len(results),
                    'results': [{'detection_id': r.get('detection_id'), 
                               'object_count': len(r.get('detections', []))} for r in results]
                })
                
            except Exception as e:
                self.logger.error(f"批量检测失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/models', methods=['GET'])
        def get_models():
            """获取可用模型列表"""
            models = {
                'current_model': self.config.get('model', {}).get('model_path', ''),
                'available_models': self._scan_available_models(),
                'model_info': {
                    'confidence_threshold': self.config.get('model', {}).get('confidence_threshold', 0.5),
                    'iou_threshold': self.config.get('model', {}).get('iou_threshold', 0.45),
                    'device': self.config.get('model', {}).get('device', 'auto')
                }
            }
            return jsonify(models)
        
        @self.app.route('/api/models/switch', methods=['POST'])
        def switch_model():
            """切换模型"""
            try:
                data = request.get_json()
                model_path = data.get('model_path')
                
                if not model_path or not os.path.exists(model_path):
                    return jsonify({'error': 'Invalid model path'}), 400
                
                # 重新初始化检测器
                self.yolo_detector = YOLODetector(
                    model_path=model_path,
                    confidence_threshold=data.get('confidence_threshold', 0.5),
                    device=data.get('device', 'auto')
                )
                
                # 更新配置
                self.config['model']['model_path'] = model_path
                if 'confidence_threshold' in data:
                    self.config['model']['confidence_threshold'] = data['confidence_threshold']
                
                return jsonify({'status': 'success', 'message': f'模型切换成功: {model_path}'})
                
            except Exception as e:
                self.logger.error(f"模型切换失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/stats', methods=['GET'])
        def get_stats():
            """获取检测服务统计信息"""
            return jsonify(self.get_stats())
    
    def _process_single_frame(self, frame: np.ndarray, stream_id: str, timestamp: float, config: Dict) -> List[Dict]:
        """调用所有已加载的算法插件对单帧进行推理，返回原始结果列表"""
        start_time = time.time()

        if not self.engines:
            # 兼容旧模式：无插件时使用内置 YOLODetector
            detection_obj = self.yolo_detector.detect(stream_id, frame, timestamp, config)
            return [{
                'algo_type': 'object',
                'stream_id': stream_id,
                'timestamp': timestamp,
                'model': self.yolo_detector.model_path,
                'device': self.yolo_detector.device,
                'detections': detection_obj.detections,
                'total_objects': detection_obj.total_objects,
                'frame_path': detection_obj.frame_path,
                'processing_time': time.time() - start_time
            }]

        results: List[Dict] = []
        for engine in self.engines:
            try:
                engine_results = engine.infer(stream_id, frame, timestamp, config)
                for r in engine_results:
                    r['processing_time'] = time.time() - start_time
                    results.append(r)
                    if r.get('algo_type') == 'object':
                        self.stats['total_detections'] += 1
                        self.stats['successful_detections'] += 1
                        self._update_average_inference_time(r['processing_time'])
            except Exception as e:
                self.logger.error(f"插件 {engine.__class__.__name__} 推理失败: {e}")
        return results
    
    def _send_results_async(self, detection_result: Dict):
        """异步发送检测结果"""
        def send_worker():
            try:
                # 所有结果都发送到 analytics-service
                if self.analytics_service_url:
                    try:
                        requests.post(
                            f"{self.analytics_service_url}/api/events/detection",
                            json=detection_result,
                            timeout=5
                        )
                    except Exception as e:
                        self.logger.debug(f"analytics-service 发送失败: {e}")
                
                if detection_result.get('algo_type') == 'object':
                    if self.storage_service_url:
                        try:
                            requests.post(
                                f"{self.storage_service_url}/api/detections",
                                json=detection_result,
                                timeout=5
                            )
                        except Exception as e:
                            self.logger.debug(f"存储服务发送失败: {e}")
            except Exception as e:
                self.logger.error(f"发送检测结果失败: {e}")
        
        # 在后台线程中发送
        threading.Thread(target=send_worker, daemon=True).start()
    
    def _scan_available_models(self) -> List[str]:
        """扫描可用模型"""
        models_dir = '/app/models'
        if not os.path.exists(models_dir):
            return []
        
        model_files = []
        for file in os.listdir(models_dir):
            if file.endswith(('.pt', '.onnx', '.trt')):
                model_files.append(os.path.join(models_dir, file))
        
        return model_files
    
    def _update_average_inference_time(self, new_time: float):
        """更新平均推理时间"""
        if self.stats['successful_detections'] == 1:
            self.stats['average_inference_time'] = new_time
        else:
            # 移动平均
            alpha = 0.1
            self.stats['average_inference_time'] = (
                alpha * new_time + (1 - alpha) * self.stats['average_inference_time']
            )
    
    def _start_processing_threads(self):
        """启动处理线程"""
        # 统计更新线程
        self.stats_thread = threading.Thread(
            target=self._stats_update_loop, daemon=True
        )
        self.stats_thread.start()
    
    def _stats_update_loop(self):
        """统计信息更新循环"""
        while True:
            try:
                # 更新队列大小
                self.stats['queue_size'] = self.detection_queue.qsize()
                
                # GPU 已移除，固定为 0
                self.stats['gpu_utilization'] = 0
                
                time.sleep(10)  # 10秒更新一次
            except Exception as e:
                self.logger.error(f"统计更新错误: {e}")
                time.sleep(10)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        uptime = time.time() - self.stats['start_time']
        
        return {
            'service': 'detection',
            'uptime': uptime,
            'detections': {
                'total': self.stats['total_detections'],
                'successful': self.stats['successful_detections'],
                'failed': self.stats['failed_detections'],
                'success_rate': (
                    self.stats['successful_detections'] / max(1, self.stats['total_detections'])
                ) * 100
            },
            'performance': {
                'average_inference_time': self.stats['average_inference_time'],
                'detections_per_minute': (
                    self.stats['successful_detections'] / max(1, uptime / 60)
                ),
                'queue_size': self.stats['queue_size']
            },
            'gpu': {
                'utilization': self.stats['gpu_utilization'],
            },
            'model': {
                'path': self.config.get('model', {}).get('model_path', ''),
                'device': self.config.get('model', {}).get('device', 'auto'),
                'confidence_threshold': self.config.get('model', {}).get('confidence_threshold', 0.5)
            },
            'timestamp': time.time()
        }
    
    def start(self):
        """启动检测服务"""
        server_config = self.config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8082)
        debug = server_config.get('debug', False)
        
        self.logger.info(f"启动检测引擎服务 - {host}:{port}")
        self.logger.info(f"模型路径: {self.config.get('model', {}).get('model_path', '')}")
        self.logger.info(f"GPU启用: {self.config.get('gpu', {}).get('enabled', False)}")
        self.logger.info(f"存储服务URL: {self.storage_service_url}")
        
        self.app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )

    def _init_engines(self):
        """根据 algorithms.yml 动态加载算法插件"""
        self.engines = []
        algo_cfg_path = os.path.join(os.path.dirname(__file__), 'config', 'algorithms.yml')
        if not os.path.exists(algo_cfg_path):
            self.logger.warning(f"算法配置 {algo_cfg_path} 不存在，未加载任何插件")
            return

        with open(algo_cfg_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for item in cfg.get('enabled', []):
            engine_type = item.get('type')
            try:
                # 兼容旧配置字段名 "model"
                if 'model' in item and 'model_path' not in item:
                    item['model_path'] = item.pop('model')

                # 若 device=auto, 让引擎自己决定
                if item.get('device') == 'auto':
                    item['device'] = 'cuda:0' if torch.cuda.is_available() else 'cpu'

                mod = import_module(f"engines.{engine_type}_engine")
                EngineCls = getattr(mod, f"{engine_type.capitalize()}Engine")
                engine = EngineCls(**item)
                self.engines.append(engine)
                self.logger.info(f"✅ 加载算法插件: {engine_type}")
            except Exception as e:
                self.logger.error(f"❌ 加载插件 {engine_type} 失败: {e}")

    # ------------------- 新增辅助方法 -------------------
    def _object_plugin_enabled(self) -> bool:
        """检查 algorithms.yml 是否启用了 type=object 插件"""
        algo_cfg_path = os.path.join(os.path.dirname(__file__), 'config', 'algorithms.yml')
        if not os.path.exists(algo_cfg_path):
            return False
        try:
            with open(algo_cfg_path, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            for item in cfg.get('enabled', []):
                if str(item.get('type')).lower() == 'object':
                    return True
        except Exception:
            # 配置解析失败时，保守返回 False 以继续加载内置模型
            pass
        return False

def main():
    """检测服务启动入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='检测引擎服务')
    parser.add_argument('--config', default='config/detection_config.json', help='配置文件路径')
    parser.add_argument('--port', type=int, default=8082, help='服务端口')
    parser.add_argument('--host', default='0.0.0.0', help='服务主机')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    # 创建检测服务实例
    service = DetectionService(args.config)
    
    # 覆盖配置
    if args.port:
        service.config['server']['port'] = args.port
    if args.host:
        service.config['server']['host'] = args.host
    if args.debug:
        service.config['server']['debug'] = True
    
    # 启动服务
    service.start()

if __name__ == '__main__':
    main() 