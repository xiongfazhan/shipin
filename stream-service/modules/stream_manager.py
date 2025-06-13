#!/usr/bin/env python3
"""
流管理器模块
负责管理视频流的创建、删除、状态监控等功能
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue
import cv2
from concurrent.futures import ThreadPoolExecutor
import importlib.util, os, sys

logger = logging.getLogger(__name__)

class StreamStatus(Enum):
    """流状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"

class StreamType(Enum):
    """流类型枚举"""
    RTMP = "rtmp"
    RTSP = "rtsp"
    HTTP = "http"
    FILE = "file"
    CAMERA = "camera"

@dataclass
class StreamInfo:
    """流信息数据类"""
    stream_id: str
    name: str
    url: str
    stream_type: StreamType
    status: StreamStatus
    created_at: float
    updated_at: float
    description: Optional[str] = None  # 添加 description 字段
    interval: float = 2.0  # 帧提取间隔（秒）
    risk_level: str = "MEDIUM"
    error_message: Optional[str] = None
    frame_count: int = 0
    last_frame_time: Optional[float] = None
    process: Optional[Any] = None  # 占位，用于兼容进程/线程句柄
    # 新增: 保存任意运行时配置，默认空字典
    config: Dict[str, Any] = field(default_factory=dict)

    # 新增: 判断流是否处于运行状态
    def is_running(self) -> bool:
        return self.status == StreamStatus.RUNNING

class StreamWorker:
    """流处理工作器"""
    
    def __init__(self, stream_info: StreamInfo, frame_callback=None, frame_filter=None):
        default_filter = None
        if frame_filter is None:
            # 尝试动态加载 filters/frame_filter.py（位于上级目录）
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            filter_path = os.path.join(base_dir, 'filters', 'frame_filter.py')
            if os.path.exists(filter_path):
                spec = importlib.util.spec_from_file_location('frame_filter', filter_path)
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)  # type: ignore
                    if hasattr(module, 'get_frame_filter'):
                        default_filter = module.get_frame_filter()
                except Exception:
                    default_filter = None
            else:
                # 最后尝试直接 import frame_filter (若已在路径内)
                try:
                    from frame_filter import get_frame_filter as _gff  # type: ignore
                    default_filter = _gff()
                except Exception:
                    default_filter = None

        # 优先使用传入的过滤器；否则使用动态加载到的全局实例；仍失败则创建占位对象
        self.frame_filter = frame_filter or default_filter or self._create_dummy_filter()

        self.stream_info = stream_info
        self.frame_callback = frame_callback
        self.is_running = False
        self.capture = None
        self.thread = None
        self.frame_queue = queue.Queue(maxsize=10)
        
    def start(self):
        """启动流处理"""
        if self.is_running:
            return False
            
        self.is_running = True
        self.thread = threading.Thread(target=self._process_stream)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"流处理器启动: {self.stream_info.stream_id}")
        return True
    
    def stop(self):
        """停止流处理"""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        if self.capture:
            self.capture.release()
        
        logger.info(f"流处理器停止: {self.stream_info.stream_id}")
    
    def _process_stream(self):
        """处理视频流的主循环"""
        try:
            # 根据流类型初始化捕获器
            if self.stream_info.stream_type == StreamType.CAMERA:
                self.capture = cv2.VideoCapture(int(self.stream_info.url))
            else:
                self.capture = cv2.VideoCapture(self.stream_info.url)
            
            if not self.capture.isOpened():
                raise Exception(f"无法打开视频流: {self.stream_info.url}")
            
            self.stream_info.status = StreamStatus.RUNNING
            last_process_time = 0
            
            while self.is_running:
                ret, frame = self.capture.read()
                if not ret:
                    logger.warning(f"[{self.stream_info.stream_id}] read frame failed")
                    time.sleep(0.1)
                    continue
                
                logger.debug(f"[{self.stream_info.stream_id}] read ok")
                
                current_time = time.time()
                self.stream_info.frame_count += 1
                self.stream_info.last_frame_time = current_time
                
                # 根据间隔决定是否处理帧
                if current_time - last_process_time >= self.stream_info.interval:
                    try:
                        # 将帧放入队列
                        if not self.frame_queue.full():
                            self.frame_queue.put({
                                'frame': frame,
                                'timestamp': current_time,
                                'stream_id': self.stream_info.stream_id
                            }, block=False)
                        
                        # 调用回调函数
                        if self.frame_callback:
                            self.frame_callback(frame, self.stream_info.stream_id, current_time)
                        
                        last_process_time = current_time
                        
                        if self.frame_filter.should_process(self.stream_info.stream_id, frame):
                            logger.debug(f"[{self.stream_info.stream_id}] enqueue to detection")
                        else:
                            logger.debug(f"[{self.stream_info.stream_id}] filtered")
                        
                    except Exception as e:
                        logger.error(f"处理帧异常: {e}")
                
                # 控制帧率
                time.sleep(0.033)  # 约30fps
                
        except Exception as e:
            logger.error(f"流处理异常: {e}")
            self.stream_info.status = StreamStatus.ERROR
            self.stream_info.error_message = str(e)
        finally:
            if self.capture:
                self.capture.release()

    def _create_dummy_filter(self):
        """创建一个最小实现，避免因缺失 filter 而报错"""
        class _Dummy:
            def should_process(self, *_, **__):
                return True

            def get_stream_config(self, *_, **__):
                return {}

        return _Dummy()

class StreamManager:
    """流管理器主类"""
    
    def __init__(self, max_concurrent_streams: int = 10):
        self.streams: Dict[str, StreamInfo] = {}
        self.workers: Dict[str, StreamWorker] = {}
        self.max_concurrent_streams = max_concurrent_streams
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_streams)
        self._lock = threading.Lock()
        
    def add_stream(self, stream_config: Dict[str, Any]) -> str:
        """添加新的视频流"""
        try:
            # 验证配置
            required_fields = ['name', 'url', 'type']
            for fld in required_fields:
                if fld not in stream_config:
                    raise ValueError(f"缺少必要字段: {fld}")
            
            # 检查并发流数量限制
            active_streams = len([s for s in self.streams.values() 
                                if s.status in [StreamStatus.RUNNING, StreamStatus.STARTING]])
            if active_streams >= self.max_concurrent_streams:
                raise ValueError(f"超过最大并发流数量限制: {self.max_concurrent_streams}")
            
            # 生成流ID (优先使用 stream_id 字段，其次 id，最后随机)
            stream_id = (
                stream_config.get('stream_id')
                or stream_config.get('id')
                or str(uuid.uuid4())
            )
            
            # 风险等级映射，增加中文兼容
            risk_map = {
                "high": "high", "高": "high",
                "medium": "medium", "中": "medium",
                "low": "low", "低": "low"
            }
            
            stream_config['risk_level'] = risk_map.get(
                str(stream_config.get('risk_level', 'medium')).lower(), 
                'medium'
            )
            
            # 创建流信息
            stream_info = StreamInfo(
                stream_id=stream_id,
                name=stream_config['name'],
                url=stream_config['url'],
                stream_type=StreamType(stream_config['type']),
                status=StreamStatus.STOPPED,
                created_at=time.time(),
                updated_at=time.time(),
                interval=stream_config.get('interval', 2.0),
                risk_level=stream_config['risk_level'],
                description=stream_config.get('description')  # 保存 description
            )
            
            with self._lock:
                self.streams[stream_id] = stream_info
            
            logger.info(f"添加视频流: {stream_id} - {stream_config['name']}")
            return stream_id
            
        except Exception as e:
            logger.error(f"添加流失败: {e}")
            raise
    
    def remove_stream(self, stream_id: str) -> bool:
        """删除视频流"""
        try:
            with self._lock:
                if stream_id not in self.streams:
                    return False
                
                # 停止工作器
                if stream_id in self.workers:
                    self.workers[stream_id].stop()
                    del self.workers[stream_id]
                
                # 删除流信息
                del self.streams[stream_id]
            
            logger.info(f"删除视频流: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除流失败: {e}")
            return False
    
    def start_stream(self, stream_id: str, frame_callback=None) -> bool:
        """启动视频流"""
        try:
            with self._lock:
                if stream_id not in self.streams:
                    return False
                
                stream_info = self.streams[stream_id]
                
                if stream_info.status == StreamStatus.RUNNING:
                    return True
                
                # 创建并启动工作器，并注入全局帧过滤器（若有）
                try:
                    from filters.frame_filter import get_frame_filter as _gff
                    global_filter = _gff()
                except ModuleNotFoundError:
                    global_filter = None

                # 创建并启动工作器
                worker = StreamWorker(stream_info, frame_callback, frame_filter=global_filter)
                if worker.start():
                    self.workers[stream_id] = worker
                    stream_info.status = StreamStatus.STARTING
                    stream_info.updated_at = time.time()
                    
                    logger.info(f"启动视频流: {stream_id}")
                    return True
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"启动流失败: {e}")
            return False
    
    def stop_stream(self, stream_id: str) -> bool:
        """停止视频流"""
        try:
            with self._lock:
                if stream_id not in self.streams:
                    return False
                
                stream_info = self.streams[stream_id]
                
                # 停止工作器
                if stream_id in self.workers:
                    self.workers[stream_id].stop()
                    del self.workers[stream_id]
                
                stream_info.status = StreamStatus.STOPPED
                stream_info.updated_at = time.time()
            
            logger.info(f"停止视频流: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止流失败: {e}")
            return False
    
    def get_stream(self, stream_id: str) -> Optional[StreamInfo]:
        """获取流信息"""
        return self.streams.get(stream_id)
    
    def get_all_streams(self) -> List[StreamInfo]:
        """获取所有流信息"""
        return list(self.streams.values())
    
    def get_stream_status(self, stream_id: str) -> Optional[StreamStatus]:
        """获取流状态"""
        stream_info = self.streams.get(stream_id)
        return stream_info.status if stream_info else None
    
    def update_stream_config(self, stream_id: str, config: Dict[str, Any]) -> bool:
        """更新流配置"""
        try:
            with self._lock:
                if stream_id not in self.streams:
                    return False
                
                stream_info = self.streams[stream_id]
                
                # 更新可修改的配置
                if 'interval' in config:
                    stream_info.interval = config['interval']
                if 'risk_level' in config:
                    stream_info.risk_level = config['risk_level']
                if 'name' in config:
                    stream_info.name = config['name']
                
                stream_info.updated_at = time.time()
            
            logger.info(f"更新流配置: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新流配置失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_streams = len(self.streams)
        running_streams = len([s for s in self.streams.values() if s.status == StreamStatus.RUNNING])
        error_streams = len([s for s in self.streams.values() if s.status == StreamStatus.ERROR])
        
        total_frames = sum(s.frame_count for s in self.streams.values())
        
        return {
            'total_streams': total_streams,
            'running_streams': running_streams,
            'error_streams': error_streams,
            'stopped_streams': total_streams - running_streams - error_streams,
            'total_frames_processed': total_frames,
            'max_concurrent_streams': self.max_concurrent_streams
        }
    
    def cleanup(self):
        """清理资源"""
        logger.info("清理流管理器资源...")
        
        # 停止所有流
        stream_ids = list(self.streams.keys())
        for stream_id in stream_ids:
            self.stop_stream(stream_id)
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        logger.info("流管理器资源清理完成")

    def __del__(self):
        """析构函数"""
        self.cleanup()

    # ------------------------ 新增辅助方法 ------------------------
    def get_running_streams(self):
        """返回所有处于 RUNNING 状态的流 (stream_id, stream_info) 列表"""
        with self._lock:
            return [
                (sid, info) for sid, info in self.streams.items()
                if info.status == StreamStatus.RUNNING
            ]

    def get_active_stream_count(self) -> int:
        """获取当前运行中的流数量"""
        with self._lock:
            return len([info for info in self.streams.values() if info.status == StreamStatus.RUNNING])

    def get_frame_from_buffer(self, stream_id: str):
        """安全地从指定流的帧缓冲区获取一帧 (若无可用则返回 None)"""
        worker = self.workers.get(stream_id)
        if not worker:
            return None
        try:
            item = worker.frame_queue.get_nowait()
            return item.get('frame') if isinstance(item, dict) else item
        except queue.Empty:
            return None