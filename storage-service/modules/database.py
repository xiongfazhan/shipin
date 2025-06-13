#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作模块
负责检测结果的存储和查询
"""

import sqlite3
import json
import time
import threading
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import logging

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "results.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._local = threading.local()
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 检测结果表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS detection_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stream_id TEXT NOT NULL,
                        stream_name TEXT,
                        timestamp REAL NOT NULL,
                        processing_time REAL,
                        total_objects INTEGER DEFAULT 0,
                        detections TEXT,  -- JSON格式存储检测详情
                        frame_shape TEXT, -- JSON格式存储帧尺寸
                        frame_path TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_stream_timestamp 
                    ON detection_results(stream_id, timestamp DESC)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON detection_results(timestamp DESC)
                ''')
                
                # 流状态表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stream_status (
                        stream_id TEXT PRIMARY KEY,
                        stream_name TEXT,
                        is_running BOOLEAN DEFAULT FALSE,
                        last_active REAL,
                        total_frames INTEGER DEFAULT 0,
                        total_detections INTEGER DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 视频流配置表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stream_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stream_id TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        type TEXT DEFAULT 'file',
                        risk_level TEXT DEFAULT '中',
                        description TEXT,
                        enabled BOOLEAN DEFAULT TRUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建stream_configs索引
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_stream_configs_enabled 
                    ON stream_configs(enabled)
                ''')
                
                conn.commit()
                self.logger.info("数据库初始化完成")
                
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（线程安全）"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=10.0
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise
    
    def save_detection_result(self, result: Dict) -> bool:
        """保存检测结果"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO detection_results (
                        stream_id, stream_name, timestamp, processing_time,
                        total_objects, detections, frame_shape, frame_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result.get('stream_id'),
                    result.get('stream_name'),
                    result.get('timestamp'),
                    result.get('processing_time'),
                    result.get('total_objects', 0),
                    json.dumps(result.get('detections', []), ensure_ascii=False),
                    json.dumps(result.get('frame_shape'), ensure_ascii=False) if result.get('frame_shape') else None,
                    result.get('frame_path')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"保存检测结果失败: {e}")
            return False
    
    def get_latest_results(self, limit: int = 100, stream_id: Optional[str] = None) -> List[Dict]:
        """获取最新检测结果"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if stream_id:
                    query = '''
                        SELECT * FROM detection_results 
                        WHERE stream_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    '''
                    cursor.execute(query, (stream_id, limit))
                else:
                    query = '''
                        SELECT * FROM detection_results 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    '''
                    cursor.execute(query, (limit,))
                
                rows = cursor.fetchall()
                results = []
                
                for row in rows:
                    result = {
                        'id': row['id'],
                        'stream_id': row['stream_id'],
                        'stream_name': row['stream_name'],
                        'timestamp': row['timestamp'],
                        'processing_time': row['processing_time'],
                        'total_objects': row['total_objects'],
                        'detections': json.loads(row['detections']) if row['detections'] else [],
                        'frame_shape': json.loads(row['frame_shape']) if row['frame_shape'] else None,
                        'frame_path': row['frame_path'],
                        'created_at': row['created_at']
                    }
                    results.append(result)
                
                return results
                
        except Exception as e:
            self.logger.error(f"获取检测结果失败: {e}")
            return []
    
    def get_results_by_time_range(self, start_time: float, end_time: float, 
                                  stream_id: Optional[str] = None) -> List[Dict]:
        """根据时间范围获取检测结果"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if stream_id:
                    query = '''
                        SELECT * FROM detection_results 
                        WHERE stream_id = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp DESC
                    '''
                    cursor.execute(query, (stream_id, start_time, end_time))
                else:
                    query = '''
                        SELECT * FROM detection_results 
                        WHERE timestamp BETWEEN ? AND ?
                        ORDER BY timestamp DESC
                    '''
                    cursor.execute(query, (start_time, end_time))
                
                rows = cursor.fetchall()
                results = []
                
                for row in rows:
                    result = {
                        'id': row['id'],
                        'stream_id': row['stream_id'],
                        'stream_name': row['stream_name'],
                        'timestamp': row['timestamp'],
                        'processing_time': row['processing_time'],
                        'total_objects': row['total_objects'],
                        'detections': json.loads(row['detections']) if row['detections'] else [],
                        'frame_shape': json.loads(row['frame_shape']) if row['frame_shape'] else None,
                        'frame_path': row['frame_path'],
                        'created_at': row['created_at']
                    }
                    results.append(result)
                
                return results
                
        except Exception as e:
            self.logger.error(f"获取时间范围检测结果失败: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 总检测结果数
                cursor.execute('SELECT COUNT(*) as total FROM detection_results')
                total_results = cursor.fetchone()['total']
                
                # 总检测对象数
                cursor.execute('SELECT SUM(total_objects) as total FROM detection_results')
                total_objects = cursor.fetchone()['total'] or 0
                
                # 最近1小时的结果数
                one_hour_ago = time.time() - 3600
                cursor.execute(
                    'SELECT COUNT(*) as recent FROM detection_results WHERE timestamp > ?',
                    (one_hour_ago,)
                )
                recent_results = cursor.fetchone()['recent']
                
                # 平均处理时间
                cursor.execute('SELECT AVG(processing_time) as avg_time FROM detection_results')
                avg_processing_time = cursor.fetchone()['avg_time'] or 0
                
                # 活跃流数量
                cursor.execute('SELECT COUNT(DISTINCT stream_id) as streams FROM detection_results')
                unique_streams = cursor.fetchone()['streams']
                
                return {
                    'total_results': total_results,
                    'total_objects': total_objects,
                    'recent_results': recent_results,
                    'avg_processing_time': avg_processing_time,
                    'unique_streams': unique_streams
                }
                
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {
                'total_results': 0,
                'total_objects': 0, 
                'recent_results': 0,
                'avg_processing_time': 0,
                'unique_streams': 0
            }
    
    def clear_results(self, stream_id: Optional[str] = None, 
                     before_timestamp: Optional[float] = None) -> int:
        """清除检测结果"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if stream_id and before_timestamp:
                    cursor.execute(
                        'DELETE FROM detection_results WHERE stream_id = ? AND timestamp < ?',
                        (stream_id, before_timestamp)
                    )
                elif stream_id:
                    cursor.execute(
                        'DELETE FROM detection_results WHERE stream_id = ?',
                        (stream_id,)
                    )
                elif before_timestamp:
                    cursor.execute(
                        'DELETE FROM detection_results WHERE timestamp < ?',
                        (before_timestamp,)
                    )
                else:
                    cursor.execute('DELETE FROM detection_results')
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"已清除 {deleted_count} 条检测结果")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"清除检测结果失败: {e}")
            return 0
    
    def get_detection_classes(self) -> List[str]:
        """获取所有检测到的类别"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT DISTINCT detections FROM detection_results WHERE detections IS NOT NULL')
                rows = cursor.fetchall()
                
                classes = set()
                for row in rows:
                    try:
                        detections = json.loads(row['detections'])
                        for detection in detections:
                            if 'class_name' in detection:
                                classes.add(detection['class_name'])
                    except (json.JSONDecodeError, TypeError):
                        continue
                
                return sorted(list(classes))
                
        except Exception as e:
            self.logger.error(f"获取检测类别失败: {e}")
            return []
    
    # 视频流配置管理方法
    
    def save_stream_config(self, config: Dict) -> bool:
        """保存单个视频流配置"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO stream_configs (
                        stream_id, name, url, type, risk_level, description, enabled, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    config.get('stream_id'),
                    config.get('name'),
                    config.get('url'),
                    config.get('type', 'file'),
                    config.get('risk_level', '中'),
                    config.get('description', ''),
                    config.get('enabled', True)
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"保存视频流配置失败: {e}")
            return False
    
    def get_stream_configs(self, enabled_only: bool = False) -> List[Dict]:
        """获取视频流配置列表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if enabled_only:
                    query = 'SELECT * FROM stream_configs WHERE enabled = 1 ORDER BY created_at'
                else:
                    query = 'SELECT * FROM stream_configs ORDER BY created_at'
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                configs = []
                for row in rows:
                    config = {
                        'id': row['id'],
                        'stream_id': row['stream_id'],
                        'name': row['name'],
                        'url': row['url'],
                        'type': row['type'],
                        'risk_level': row['risk_level'],
                        'description': row['description'],
                        'enabled': bool(row['enabled']),
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                    configs.append(config)
                
                return configs
                
        except Exception as e:
            self.logger.error(f"获取视频流配置失败: {e}")
            return []
    
    def update_stream_config(self, stream_id: str, updates: Dict) -> bool:
        """更新视频流配置"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建UPDATE语句
                set_clauses = []
                values = []
                
                for key, value in updates.items():
                    if key in ['name', 'url', 'type', 'risk_level', 'description', 'enabled']:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    return False
                
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                values.append(stream_id)
                
                query = f"UPDATE stream_configs SET {', '.join(set_clauses)} WHERE stream_id = ?"
                cursor.execute(query, values)
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"更新视频流配置失败: {e}")
            return False
    
    def delete_stream_config(self, stream_id: str) -> bool:
        """删除视频流配置"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM stream_configs WHERE stream_id = ?', (stream_id,))
                conn.commit()
                
                self.logger.info(f"已删除视频流配置: {stream_id}")
                return cursor.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"删除视频流配置失败: {e}")
            return False
    
    def bulk_save_stream_configs(self, configs: List[Dict]) -> int:
        """批量保存视频流配置"""
        success_count = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for config in configs:
                    try:
                        # 确保有必要的字段
                        if 'stream_id' not in config and 'name' in config:
                            config['stream_id'] = config['name']
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO stream_configs (
                                stream_id, name, url, type, risk_level, description, enabled, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (
                            config.get('stream_id'),
                            config.get('name'),
                            config.get('url'),
                            config.get('type', 'file'),
                            config.get('risk_level', '中'),
                            config.get('description', ''),
                            config.get('enabled', True)
                        ))
                        success_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"保存配置失败 {config.get('name', 'unknown')}: {e}")
                        continue
                
                conn.commit()
                self.logger.info(f"批量保存视频流配置完成: {success_count}/{len(configs)}")
                
        except Exception as e:
            self.logger.error(f"批量保存视频流配置失败: {e}")
        
        return success_count
    
    def clear_stream_configs(self) -> int:
        """清除所有视频流配置"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM stream_configs')
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"已清除 {deleted_count} 个视频流配置")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"清除视频流配置失败: {e}")
            return 0

# 全局数据库管理器实例
db_manager = DatabaseManager() 