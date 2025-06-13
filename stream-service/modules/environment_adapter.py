"""
环境适配器
在CPU开发环境中模拟GPU生产环境功能
确保开发和部署的一致性
"""

import os
import json
import logging
import threading
import time
import numpy as np
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class EnvironmentDetector:
    """环境检测器"""
    
    @staticmethod
    def is_cuda_available() -> bool:
        """检测CUDA是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    @staticmethod
    def get_gpu_count() -> int:
        """获取GPU数量"""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.device_count()
            return 0
        except ImportError:
            return 0
    
    @staticmethod
    def detect_environment() -> str:
        """检测当前环境类型"""
        if EnvironmentDetector.is_cuda_available():
            gpu_count = EnvironmentDetector.get_gpu_count()
            if gpu_count >= 4:
                return "production"  # 生产环境
            elif gpu_count >= 1:
                return "staging"     # 预发布环境
        return "development"         # 开发环境


class MockGPUWorker:
    """模拟GPU工作器（用于CPU开发环境）"""
    
    def __init__(self, gpu_id: int, model_path: str, config: Dict[str, Any]):
        self.gpu_id = gpu_id
        self.model_path = model_path
        self.config = config
        self.device = f"mock_cuda:{gpu_id}"
        
        # 性能统计
        self.stats = {
            'processed_frames': 0,
            'processing_time': 0.0,
            'last_fps': 0.0,
            'gpu_utilization': 0.0
        }
        
        # 模拟处理时间（基于真实GPU性能）
        self.processing_time_per_frame = 0.01  # 10ms/帧（模拟RTX 3090性能）
        
        logger.info(f"Mock GPU {gpu_id}: 初始化完成")
    
    def add_frame(self, frame: np.ndarray, metadata: Dict[str, Any]) -> bool:
        """模拟添加帧"""
        # 模拟队列管理
        return True
    
    def get_result(self, timeout: float = 0.001) -> Optional[Dict[str, Any]]:
        """模拟获取结果"""
        # 模拟处理延迟
        time.sleep(self.processing_time_per_frame)
        
        # 模拟检测结果
        mock_result = {
            'result': self._generate_mock_detection(),
            'metadata': {'stream_id': 'mock_stream', 'timestamp': time.time()},
            'gpu_id': self.gpu_id,
            'processing_time': self.processing_time_per_frame
        }
        
        # 更新统计
        self.stats['processed_frames'] += 1
        self.stats['processing_time'] += self.processing_time_per_frame
        self.stats['last_fps'] = 1.0 / self.processing_time_per_frame
        self.stats['gpu_utilization'] = min(85.0, self.stats['last_fps'])  # 模拟利用率
        
        return mock_result
    
    def _generate_mock_detection(self) -> List[Dict[str, Any]]:
        """生成模拟检测结果"""
        # 随机生成0-3个检测框
        import random
        detection_count = random.randint(0, 3)
        
        detections = []
        for i in range(detection_count):
            detection = {
                'class': random.choice(['person', 'car', 'bicycle', 'dog']),
                'confidence': random.uniform(0.5, 0.95),
                'bbox': [
                    random.randint(50, 200),   # x1
                    random.randint(50, 200),   # y1  
                    random.randint(250, 500),  # x2
                    random.randint(250, 400)   # y2
                ]
            }
            detections.append(detection)
        
        return detections
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return self.stats.copy()


class MockMultiGPUProcessor:
    """模拟多GPU处理器（用于CPU开发环境）"""
    
    def __init__(self, config_path: str = "config/development_config.json"):
        self.config = self._load_config(config_path)
        self.gpu_workers = {}
        self.stream_gpu_mapping = {}
        
        # 从配置中获取模拟GPU数量
        mock_gpu_count = self.config.get('development', {}).get('mock_gpu_count', 8)
        
        # 初始化模拟GPU工作器
        self._init_mock_gpu_workers(mock_gpu_count)
        
        logger.info(f"模拟多GPU处理器初始化完成，模拟{len(self.gpu_workers)}个GPU")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return {}
    
    def _init_mock_gpu_workers(self, gpu_count: int):
        """初始化模拟GPU工作器"""
        yolo_config = self.config.get('yolo', {})
        model_path = yolo_config.get('model_path', 'models/yolov8n.pt')
        
        for gpu_id in range(gpu_count):
            worker = MockGPUWorker(gpu_id, model_path, yolo_config)
            self.gpu_workers[gpu_id] = worker
            logger.info(f"Mock GPU {gpu_id} 工作器启动成功")
    
    def process_frame(self, stream_id: str, frame: np.ndarray, 
                     metadata: Dict[str, Any]) -> bool:
        """处理单帧（模拟）"""
        # 选择GPU（轮询）
        gpu_id = len(self.stream_gpu_mapping) % len(self.gpu_workers)
        self.stream_gpu_mapping[stream_id] = gpu_id
        
        # 模拟提交到GPU
        return self.gpu_workers[gpu_id].add_frame(frame, metadata)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        stats = {
            'total_gpus': len(self.gpu_workers),
            'active_streams': len(self.stream_gpu_mapping),
            'gpu_stats': {},
            'environment': 'development_mock'
        }
        
        for gpu_id, worker in self.gpu_workers.items():
            stats['gpu_stats'][f'gpu_{gpu_id}'] = worker.get_stats()
        
        return stats


class EnvironmentAdapter:
    """环境适配器主类"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.environment = EnvironmentDetector.detect_environment()
        self.config = self._load_environment_config()
        
        logger.info(f"环境检测结果: {self.environment}")
        
        # 初始化处理器
        self.processor = self._init_processor()
    
    def _load_environment_config(self) -> Dict[str, Any]:
        """根据环境加载相应配置"""
        config_files = {
            'development': 'development_config.json',
            'staging': 'performance_config.json', 
            'production': 'production_config.json'
        }
        
        config_file = self.config_dir / config_files.get(
            self.environment, 'development_config.json'
        )
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"加载配置文件: {config_file}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            return {}
    
    def _init_processor(self):
        """根据环境初始化相应的处理器"""
        if self.environment == 'production':
            # 生产环境使用真实GPU处理器
            try:
                from modules.multi_gpu_processor import MultiGPUProcessor
                return MultiGPUProcessor("config/production_config.json")
            except Exception as e:
                logger.warning(f"无法初始化多GPU处理器，回退到模拟模式: {e}")
                return MockMultiGPUProcessor("config/development_config.json")
        
        elif self.environment == 'staging':
            # 预发布环境，尝试使用GPU，失败则模拟
            try:
                from modules.multi_gpu_processor import MultiGPUProcessor
                return MultiGPUProcessor("config/performance_config.json")
            except Exception as e:
                logger.warning(f"预发布环境GPU初始化失败，使用模拟模式: {e}")
                return MockMultiGPUProcessor("config/development_config.json")
        
        else:
            # 开发环境使用模拟处理器
            return MockMultiGPUProcessor("config/development_config.json")
    
    def process_frame(self, stream_id: str, frame: np.ndarray, 
                     metadata: Dict[str, Any]) -> bool:
        """统一的帧处理接口"""
        return self.processor.process_frame(stream_id, frame, metadata)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        stats = self.processor.get_system_stats()
        stats['environment_type'] = self.environment
        stats['cuda_available'] = EnvironmentDetector.is_cuda_available()
        stats['gpu_count'] = EnvironmentDetector.get_gpu_count()
        return stats
    
    def get_performance_estimate(self, target_streams: int) -> Dict[str, Any]:
        """获取性能预估"""
        if self.environment == 'production':
            # 基于RTX 3090实际性能计算
            gpu_count = EnvironmentDetector.get_gpu_count()
            frames_per_second_per_gpu = 150  # RTX 3090约150fps
            total_capacity = gpu_count * frames_per_second_per_gpu
            
            fps_per_stream = 5  # 每路5fps检测
            max_streams = total_capacity // fps_per_stream
            
            utilization = (target_streams * fps_per_stream) / total_capacity * 100
            
            return {
                'max_supported_streams': max_streams,
                'target_streams': target_streams,
                'gpu_utilization_percent': utilization,
                'feasible': target_streams <= max_streams,
                'performance_margin_percent': ((max_streams - target_streams) / max_streams * 100) if target_streams <= max_streams else 0
            }
        
        elif self.environment == 'development':
            # 开发环境基于模拟数据
            return {
                'max_supported_streams': 100,  # 模拟值
                'target_streams': target_streams,
                'gpu_utilization_percent': 50,  # 模拟值
                'feasible': True,
                'performance_margin_percent': 50,
                'note': '这是基于模拟的预估值，实际性能需要在生产环境测试'
            }
        
        else:
            # 预发布环境
            return {
                'max_supported_streams': 20,
                'target_streams': target_streams,
                'gpu_utilization_percent': target_streams * 5,
                'feasible': target_streams <= 20,
                'performance_margin_percent': max(0, (20 - target_streams) / 20 * 100)
            }
    
    def validate_production_readiness(self) -> Dict[str, Any]:
        """验证生产环境就绪状态"""
        checks = {
            'cuda_available': EnvironmentDetector.is_cuda_available(),
            'sufficient_gpus': EnvironmentDetector.get_gpu_count() >= 4,
            'model_files_exist': self._check_model_files(),
            'dependencies_installed': self._check_dependencies(),
            'config_files_valid': self._check_config_files()
        }
        
        all_passed = all(checks.values())
        
        return {
            'ready_for_production': all_passed,
            'checks': checks,
            'current_environment': self.environment,
            'recommendations': self._get_recommendations(checks)
        }
    
    def _check_model_files(self) -> bool:
        """检查模型文件"""
        model_path = Path("models/yolov8n.pt")
        return model_path.exists()
    
    def _check_dependencies(self) -> bool:
        """检查依赖包"""
        required_packages = ['torch', 'ultralytics', 'opencv-python']
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                return False
        return True
    
    def _check_config_files(self) -> bool:
        """检查配置文件"""
        required_configs = [
            'development_config.json',
            'performance_config.json', 
            'production_config.json'
        ]
        
        for config_file in required_configs:
            if not (self.config_dir / config_file).exists():
                return False
        return True
    
    def _get_recommendations(self, checks: Dict[str, bool]) -> List[str]:
        """获取改进建议"""
        recommendations = []
        
        if not checks['cuda_available']:
            recommendations.append("安装CUDA驱动和PyTorch GPU版本")
        
        if not checks['sufficient_gpus']:
            recommendations.append("至少需要4个GPU用于生产环境")
        
        if not checks['model_files_exist']:
            recommendations.append("下载YOLO模型文件到models/目录")
        
        if not checks['dependencies_installed']:
            recommendations.append("安装所有必需的Python依赖包")
        
        if not checks['config_files_valid']:
            recommendations.append("确保所有配置文件存在且格式正确")
        
        return recommendations


# 全局环境适配器实例
environment_adapter = None

def get_environment_adapter() -> EnvironmentAdapter:
    """获取全局环境适配器实例"""
    global environment_adapter
    if environment_adapter is None:
        environment_adapter = EnvironmentAdapter()
    return environment_adapter


def init_environment_adapter(config_dir: str = "config") -> EnvironmentAdapter:
    """初始化环境适配器"""
    global environment_adapter
    environment_adapter = EnvironmentAdapter(config_dir)
    return environment_adapter


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    adapter = EnvironmentAdapter()
    
    print(f"当前环境: {adapter.environment}")
    print(f"系统统计: {adapter.get_system_stats()}")
    print(f"100路流性能预估: {adapter.get_performance_estimate(100)}")
    print(f"生产就绪检查: {adapter.validate_production_readiness()}") 