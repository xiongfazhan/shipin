#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧预过滤器 - Frame Filter
实现按指定时间间隔抽帧的核心功能
"""

import time
import logging
from typing import Dict, Optional, Any
import cv2
import numpy as np

class FrameFilter:
    """帧预过滤器 - 核心抽帧逻辑"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 记录每个流的最后处理时间
        self.last_process_time = {}
        # 流配置缓存
        self.stream_configs = {}
        
    def configure_stream(self, stream_id: str, config: Dict[str, Any]):
        """配置流的抽帧参数"""
        self.stream_configs[stream_id] = {
            'frame_interval': config.get('frame_interval', 2.0),  # 默认2秒抽1帧
            'risk_level': config.get('risk_level', 'MEDIUM'),
            'enabled': config.get('enabled', True)
        }
        
        # 初始化时间记录
        if stream_id not in self.last_process_time:
            self.last_process_time[stream_id] = 0
        
        self.logger.info(f"配置流 {stream_id} 抽帧间隔: {config.get('frame_interval', 2.0)}秒")
    
    def should_process_frame(self, stream_id: str, current_time: float = None) -> bool:
        """
        判断是否应该处理当前帧
        
        Args:
            stream_id: 流ID
            current_time: 当前时间戳，如果为None则使用当前时间
            
        Returns:
            bool: True表示应该处理该帧，False表示跳过
        """
        if current_time is None:
            current_time = time.time()
        
        # 获取流配置
        stream_config = self.stream_configs.get(stream_id)
        if not stream_config or not stream_config.get('enabled', True):
            return False
        
        frame_interval = stream_config.get('frame_interval', 2.0)
        
        # 获取最后处理时间
        last_time = self.last_process_time.get(stream_id, 0)
        
        # 判断是否达到间隔时间
        if current_time - last_time >= frame_interval:
            # 更新最后处理时间
            self.last_process_time[stream_id] = current_time
            
            self.logger.debug(f"流 {stream_id} 通过时间过滤 - 间隔: {current_time - last_time:.2f}s")
            return True
        
        return False
    
    def filter_frame(self, stream_id: str, frame: np.ndarray, timestamp: float = None) -> Optional[Dict[str, Any]]:
        """
        过滤帧数据
        
        Args:
            stream_id: 流ID
            frame: 帧数据
            timestamp: 时间戳
            
        Returns:
            Dict: 如果通过过滤返回帧数据包，否则返回None
        """
        if timestamp is None:
            timestamp = time.time()
        
        # 预过滤检查
        if not self.should_process_frame(stream_id, timestamp):
            return None
        
        # 构建帧数据包
        frame_data = {
            'stream_id': stream_id,
            'frame': frame,
            'timestamp': timestamp,
            'frame_shape': frame.shape,
            'filter_passed': True
        }
        
        # 记录统计信息
        stream_config = self.stream_configs.get(stream_id, {})
        frame_data['config'] = {
            'frame_interval': stream_config.get('frame_interval', 2.0),
            'risk_level': stream_config.get('risk_level', 'MEDIUM')
        }
        
        return frame_data
    
    def get_stream_stats(self, stream_id: str) -> Dict[str, Any]:
        """获取流的统计信息"""
        config = self.stream_configs.get(stream_id, {})
        last_time = self.last_process_time.get(stream_id, 0)
        current_time = time.time()
        
        return {
            'stream_id': stream_id,
            'frame_interval': config.get('frame_interval', 2.0),
            'risk_level': config.get('risk_level', 'MEDIUM'),
            'enabled': config.get('enabled', True),
            'last_process_time': last_time,
            'time_since_last_process': current_time - last_time,
            'next_process_in': max(0, config.get('frame_interval', 2.0) - (current_time - last_time))
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有流的统计信息"""
        stats = {
            'total_streams': len(self.stream_configs),
            'active_streams': len([s for s in self.stream_configs.values() if s.get('enabled', True)]),
            'streams': {}
        }
        
        for stream_id in self.stream_configs.keys():
            stats['streams'][stream_id] = self.get_stream_stats(stream_id)
        
        return stats
    
    def reset_stream_timer(self, stream_id: str):
        """重置流的计时器"""
        if stream_id in self.last_process_time:
            self.last_process_time[stream_id] = 0
            self.logger.info(f"重置流 {stream_id} 计时器")
    
    def remove_stream(self, stream_id: str):
        """移除流配置"""
        if stream_id in self.stream_configs:
            del self.stream_configs[stream_id]
        if stream_id in self.last_process_time:
            del self.last_process_time[stream_id]
        self.logger.info(f"移除流 {stream_id} 配置")

    def should_process(self, stream_id: str, frame=None, current_time: float = None) -> bool:
        """兼容旧接口: 直接代理到 should_process_frame，仅保留签名以避免调用错误"""
        return self.should_process_frame(stream_id, current_time)

    def get_stream_config(self, stream_id: str) -> Dict[str, Any]:
        """兼容旧接口: 返回流的配置字典，如果不存在则返回空 dict"""
        return self.stream_configs.get(stream_id, {}).copy()

class AdaptiveFrameFilter(FrameFilter):
    """自适应帧过滤器 - 根据风险等级动态调整"""
    
    def __init__(self):
        super().__init__()
        
        # 风险等级对应的间隔配置
        self.risk_intervals = {
            'HIGH': 0.5,    # 高风险：0.5秒1帧
            'MEDIUM': 2.0,  # 中风险：2秒1帧
            'LOW': 5.0      # 低风险：5秒1帧
        }
    
    def configure_stream(self, stream_id: str, config: Dict[str, Any]):
        """配置流参数 - 支持风险等级自适应"""
        # 兼容 dataclass RiskConfig 生成的 'level' 字段
        risk_level = config.get('risk_level')
        if not risk_level and 'level' in config:
            # RiskLevel 枚举或字符串
            lvl_val = config.pop('level')
            if hasattr(lvl_val, 'name'):
                risk_level = lvl_val.name  # Enum -> name (HIGH/MEDIUM/LOW)
            else:
                risk_level = str(lvl_val).upper()
            config['risk_level'] = risk_level
        if not risk_level:
            risk_level = 'MEDIUM'

        # 如果没有明确指定间隔，使用风险等级默认值
        if 'frame_interval' not in config:
            config['frame_interval'] = self.risk_intervals.get(risk_level, 2.0)

        super().configure_stream(stream_id, config)
        
        self.logger.info(f"自适应配置流 {stream_id} - 风险等级: {risk_level}, 间隔: {config['frame_interval']}秒")
    
    def update_risk_level(self, stream_id: str, risk_level: str):
        """动态更新流的风险等级"""
        if stream_id in self.stream_configs:
            old_interval = self.stream_configs[stream_id].get('frame_interval', 2.0)
            new_interval = self.risk_intervals.get(risk_level, 2.0)
            
            self.stream_configs[stream_id]['risk_level'] = risk_level
            self.stream_configs[stream_id]['frame_interval'] = new_interval
            
            self.logger.info(f"更新流 {stream_id} 风险等级: {risk_level}, 间隔: {old_interval}s -> {new_interval}s")
    
    def get_risk_intervals(self) -> Dict[str, float]:
        """获取风险等级间隔配置"""
        return self.risk_intervals.copy()

# 全局过滤器实例
frame_filter = AdaptiveFrameFilter()

def get_frame_filter() -> AdaptiveFrameFilter:
    """获取全局帧过滤器实例"""
    return frame_filter 