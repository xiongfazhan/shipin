#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据存储服务 - Storage Service
负责检测结果存储和数据查询
"""

import os
import sys
import time
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify
import redis
import pymongo
from pymongo import MongoClient

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'models'))

from modules.database import DatabaseManager as Database

class StorageService:
    """数据存储服务 - 专注于数据管理"""
    
    def __init__(self, config_file: str = 'config/storage_config.json'):
        self.config_file = config_file
        self.config = self._load_config()
        
        # 初始化日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Flask应用
        self.app = Flask(__name__)
        self._setup_routes()
        
        # 数据库连接
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        self.database = None
        
        # 统计信息
        self.stats = {
            'start_time': time.time(),
            'total_records': 0,
            'hot_cache_hits': 0,
            'cold_storage_queries': 0,
            'storage_usage_mb': 0
        }
        
        # 初始化数据库连接
        self._initialize_databases()
        
        # 启动清理线程
        self._start_cleanup_threads()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8083,
                'debug': False
            },
            'redis': {
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'password': None,
                'hot_data_ttl': 86400  # 1天
            },
            'mongodb': {
                'host': 'localhost',
                'port': 27017,
                'database': 'video_analysis',
                'username': None,
                'password': None,
                'warm_data_ttl': 2592000  # 30天
            },
            'storage': {
                'enable_hot_cache': True,
                'enable_cold_storage': True,
                'max_records_per_query': 1000,
                'cleanup_interval': 3600,  # 1小时
                'archive_threshold_days': 90
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/storage.log'
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
        log_file = log_config.get('file', 'logs/storage.log')
        
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
    
    def _initialize_databases(self):
        """初始化数据库连接"""
        try:
            # Redis连接 (热数据缓存)
            if self.config.get('storage', {}).get('enable_hot_cache', True):
                try:
                    redis_config = self.config.get('redis', {})
                    self.redis_client = redis.Redis(
                        host=redis_config.get('host', 'localhost'),
                        port=redis_config.get('port', 6379),
                        db=redis_config.get('db', 0),
                        password=redis_config.get('password'),
                        decode_responses=True,
                        socket_connect_timeout=2,
                        socket_timeout=2
                    )
                    # 测试连接
                    self.redis_client.ping()
                    self.logger.info("Redis连接成功")
                except Exception as e:
                    self.logger.warning(f"Redis连接失败，禁用热缓存: {e}")
                    self.redis_client = None
            
            # MongoDB连接 (温数据存储)
            if self.config.get('storage', {}).get('enable_cold_storage', True):
                try:
                    mongo_config = self.config.get('mongodb', {})
                    
                    if mongo_config.get('username'):
                        connection_string = f"mongodb://{mongo_config['username']}:{mongo_config['password']}@{mongo_config['host']}:{mongo_config['port']}/{mongo_config['database']}"
                    else:
                        connection_string = f"mongodb://{mongo_config['host']}:{mongo_config['port']}"
                    
                    self.mongo_client = MongoClient(
                        connection_string,
                        serverSelectionTimeoutMS=2000,
                        connectTimeoutMS=2000
                    )
                    self.mongo_db = self.mongo_client[mongo_config.get('database', 'video_analysis')]
                    
                    # 测试连接
                    self.mongo_client.admin.command('ping')
                    self.logger.info("MongoDB连接成功")
                    
                    # 创建索引
                    self._create_mongodb_indexes()
                except Exception as e:
                    self.logger.warning(f"MongoDB连接失败，禁用冷存储: {e}")
                    self.mongo_client = None
                    self.mongo_db = None
            
            # 初始化原有数据库模块作为兼容层
            self.database = Database()
            self.logger.info("SQLite数据库初始化成功")
            
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            # 继续运行，但功能受限
            self.database = None
    
    def _create_mongodb_indexes(self):
        """创建MongoDB索引"""
        try:
            # 检测结果集合索引
            detections_collection = self.mongo_db['detections']
            detections_collection.create_index([('stream_id', 1), ('timestamp', -1)])
            detections_collection.create_index([('detection_id', 1)], unique=True)
            detections_collection.create_index([('timestamp', -1)])
            
            # 流信息集合索引
            streams_collection = self.mongo_db['streams']
            streams_collection.create_index([('stream_id', 1)], unique=True)
            
            self.logger.info("MongoDB索引创建完成")
        except Exception as e:
            self.logger.error(f"创建MongoDB索引失败: {e}")
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """健康检查"""
            redis_status = 'connected' if self.redis_client else 'disconnected'
            mongo_status = 'connected' if self.mongo_client else 'disconnected'
            
            try:
                if self.redis_client:
                    self.redis_client.ping()
                if self.mongo_client:
                    self.mongo_client.admin.command('ping')
            except:
                redis_status = 'error' if self.redis_client else 'disconnected'
                mongo_status = 'error' if self.mongo_client else 'disconnected'
            
            return jsonify({
                'status': 'healthy',
                'service': 'storage',
                'timestamp': time.time(),
                'uptime': time.time() - self.stats['start_time'],
                'databases': {
                    'redis': redis_status,
                    'mongodb': mongo_status
                },
                'total_records': self.stats['total_records']
            })
        
        @self.app.route('/api/detections', methods=['POST'])
        def store_detection():
            """存储检测结果"""
            try:
                detection_data = request.get_json()
                
                if not detection_data or 'detection_id' not in detection_data:
                    return jsonify({'error': 'Invalid detection data'}), 400
                
                # 存储到不同层级
                result = self._store_detection_multilayer(detection_data)
                
                if result['success']:
                    self.stats['total_records'] += 1
                    return jsonify({
                        'status': 'success',
                        'detection_id': detection_data['detection_id'],
                        'storage_layers': result['layers']
                    })
                else:
                    return jsonify({'error': result['error']}), 500
                    
            except Exception as e:
                self.logger.error(f"存储检测结果失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/detections/<detection_id>', methods=['GET'])
        def get_detection(detection_id):
            """获取单个检测结果"""
            try:
                result = self._get_detection_multilayer(detection_id)
                
                if result:
                    return jsonify(result)
                else:
                    return jsonify({'error': 'Detection not found'}), 404
                    
            except Exception as e:
                self.logger.error(f"获取检测结果失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/results/latest', methods=['GET'])
        def get_latest_results():
            """获取最新检测结果"""
            try:
                limit = request.args.get('limit', 20, type=int)
                limit = min(limit, self.config.get('storage', {}).get('max_records_per_query', 1000))
                
                results = self._get_latest_results(limit)
                
                return jsonify({
                    'success': True,
                    'results': results,
                    'count': len(results),
                    'limit': limit
                })
                
            except Exception as e:
                self.logger.error(f"获取最新结果失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/results/<stream_id>', methods=['GET'])
        def get_stream_results(stream_id):
            """获取指定流的检测结果"""
            try:
                # 查询参数
                limit = request.args.get('limit', 100, type=int)
                offset = request.args.get('offset', 0, type=int)
                start_time = request.args.get('start_time', type=float)
                end_time = request.args.get('end_time', type=float)
                
                limit = min(limit, self.config.get('storage', {}).get('max_records_per_query', 1000))
                
                results = self._get_stream_results(
                    stream_id, limit, offset, start_time, end_time
                )
                
                return jsonify({
                    'success': True,
                    'stream_id': stream_id,
                    'results': results,
                    'count': len(results),
                    'limit': limit,
                    'offset': offset
                })
                
            except Exception as e:
                self.logger.error(f"获取流结果失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/stats/summary', methods=['GET'])
        def get_summary_stats():
            """获取汇总统计"""
            try:
                period = request.args.get('period', '24h')  # 24h, 7d, 30d
                
                stats = self._get_summary_statistics(period)
                
                # 兼容前端 results.js 期望的字段
                now_ts = time.time()
                one_hour_ago = now_ts - 3600
                total_results = stats.get('total_detections', 0)

                # 计算 recent_results (最近1小时)
                recent_results = 0
                if self.mongo_db:
                    try:
                        recent_results = self.mongo_db['detections'].count_documents({'timestamp': {'$gte': one_hour_ago}})
                    except Exception:
                        pass

                stats.update({
                    'success': True,
                    'total_results': total_results,
                    'total_objects': total_results,  # 若无对象总数可近似使用条数
                    'recent_results': recent_results,
                    'avg_processing_time': 0  # 暂无，后续可在 detection-service 写入再聚合
                })
                
                return jsonify(stats)
                
            except Exception as e:
                self.logger.error(f"获取汇总统计失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/streams', methods=['GET'])
        def get_active_streams():
            """获取活跃流列表"""
            try:
                streams = self._get_active_streams()
                
                return jsonify({
                    'streams': streams,
                    'count': len(streams)
                })
                
            except Exception as e:
                self.logger.error(f"获取活跃流失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/stats', methods=['GET'])
        def get_storage_stats():
            """获取存储服务统计信息"""
            return jsonify(self.get_stats())
        
        @self.app.route('/api/cleanup', methods=['POST'])
        def manual_cleanup():
            """手动触发清理"""
            try:
                result = self._cleanup_old_data()
                return jsonify({
                    'status': 'success',
                    'cleanup_result': result
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/summary', methods=['POST'])
        def store_summary():
            """存储聚合汇总结果（简化版）"""
            try:
                summary_data = request.get_json()
                if not summary_data or summary_data.get('event_type') != 'summary':
                    return jsonify({'error': 'Invalid summary data'}), 400
 
                layers = []
                # 直接写入MongoDB（如可用）
                try:
                    if self.mongo_db:
                        self.mongo_db['summaries'].insert_one(summary_data)
                        layers.append('mongodb')
                except Exception as e:
                    self.logger.debug(f"MongoDB 写入summary失败: {e}")
 
                # 可扩展写入Redis或SQLite；此处简单计数
                self.stats['total_records'] += 1
                return jsonify({'status': 'success', 'layers': layers})
            except Exception as e:
                self.logger.error(f"存储summary失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/results/clear', methods=['POST'])
        def clear_all_results():
            """清空所有检测结果（热缓存 + 冷存储 + 兼容 SQLite）"""
            try:
                cleared = {
                    'redis': 0,
                    'mongodb': 0,
                    'legacy_db': 0
                }
 
                # Redis 热缓存
                if self.redis_client:
                    try:
                        keys = self.redis_client.keys('detection:*')
                        if keys:
                            cleared['redis'] = self.redis_client.delete(*keys)
                    except Exception as e:
                        self.logger.warning(f"Redis 清理失败: {e}")
 
                # MongoDB
                if self.mongo_db:
                    try:
                        res = self.mongo_db['detections'].delete_many({})
                        cleared['mongodb'] = res.deleted_count
                    except Exception as e:
                        self.logger.warning(f"MongoDB 清理失败: {e}")
 
                # SQLite / legacy DB
                if self.database and hasattr(self.database, 'clear_results'):
                    try:
                        cleared['legacy_db'] = self.database.clear_results()
                    except Exception as e:
                        self.logger.warning(f"SQLite 清理失败: {e}")
 
                # 更新内部统计
                self.stats['total_records'] = 0
                self.stats['hot_cache_hits'] = 0
                self.stats['cold_storage_queries'] = 0
 
                return jsonify({'success': True, 'cleared': cleared})
            except Exception as e:
                self.logger.error(f"清空检测结果失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/results/summary', methods=['GET'])
        def get_results_summary():
            """按时间窗口聚合检测结果 (默认5分钟) - 供管理端汇总页面使用"""
            try:
                window_param = request.args.get('window', '5m')  # 5m, 1h, 24h, etc.
                multiplier = 60  # 默认分钟
                if window_param.endswith('m'):
                    multiplier = 60
                    base_val = window_param[:-1]
                elif window_param.endswith('h'):
                    multiplier = 3600
                    base_val = window_param[:-1]
                elif window_param.endswith('d'):
                    multiplier = 86400
                    base_val = window_param[:-1]
                else:
                    # 纯数字视为秒
                    base_val = window_param
                    multiplier = 1
                try:
                    window_seconds = int(float(base_val) * multiplier)
                except ValueError:
                    window_seconds = 300  # fallback 5 min
                end_ts = time.time()
                start_ts = end_ts - window_seconds

                summary_rows = []

                # 优先使用 MongoDB 聚合
                if self.mongo_db:
                    try:
                        detections_col = self.mongo_db['detections']
                        pipeline = [
                            {
                                '$match': {
                                    'timestamp': {
                                        '$gte': start_ts,
                                        '$lte': end_ts
                                    }
                                }
                            },
                            {
                                '$group': {
                                    '_id': '$stream_id',
                                    'total_detections': {'$sum': 1},
                                    'avg_processing_time_ms': {
                                        '$avg': {
                                            '$multiply': ['$processing_time', 1000]
                                        }
                                    }
                                }
                            },
                            {
                                '$project': {
                                    '_id': 0,
                                    'stream_id': '$_id',
                                    'total_detections': 1,
                                    'avg_processing_time_ms': {'$round': ['$avg_processing_time_ms', 2]}
                                }
                            }
                        ]
                        cursor = detections_col.aggregate(pipeline)
                        for doc in cursor:
                            doc['window_start'] = start_ts
                            doc['window_end'] = end_ts
                            doc['anomaly_count'] = doc.get('anomaly_count', 0)
                            summary_rows.append(doc)
                    except Exception as e:
                        self.logger.error(f"MongoDB 聚合汇总失败: {e}")

                # 若 MongoDB 不可用或无数据，降级到 Redis 或内存聚合
                if not summary_rows and self.redis_client:
                    try:
                        # Redis简易扫描键: detection:* 结构未定，跳过
                        pass
                    except Exception:
                        pass

                return jsonify({
                    'success': True,
                    'window': window_param,
                    'summary': summary_rows,
                    'count': len(summary_rows)
                })

            except Exception as e:
                self.logger.error(f"获取汇总结果失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def _store_detection_multilayer(self, detection_data: Dict) -> Dict:
        """多层存储检测结果"""
        layers_stored = []
        
        try:
            # Layer 1: Redis热缓存 (最新数据)
            if self.redis_client and self.config.get('storage', {}).get('enable_hot_cache', True):
                redis_key = f"detection:{detection_data['detection_id']}"
                redis_data = json.dumps(detection_data)
                ttl = self.config.get('redis', {}).get('hot_data_ttl', 86400)
                
                self.redis_client.setex(redis_key, ttl, redis_data)
                
                # 更新流最新检测时间
                stream_key = f"stream:{detection_data['stream_id']}:latest"
                self.redis_client.setex(stream_key, ttl, detection_data['timestamp'])
                
                layers_stored.append('redis')
            
            # Layer 2: MongoDB温存储 (历史数据)
            if self.mongo_db and self.config.get('storage', {}).get('enable_cold_storage', True):
                detections_collection = self.mongo_db['detections']
                
                # 添加存储时间戳
                mongo_data = detection_data.copy()
                mongo_data['stored_at'] = datetime.utcnow()
                
                detections_collection.insert_one(mongo_data)
                layers_stored.append('mongodb')
            
            # Layer 3: 兼容原有数据库 (可选)
            if self.database:
                try:
                    if hasattr(self.database, 'store_detection_result'):
                        # 兼容旧方法名
                        self.database.store_detection_result(detection_data)
                    else:
                        # 新方法名 save_detection_result
                        self.database.save_detection_result(detection_data)
                    layers_stored.append('legacy_db')
                except Exception as e:
                    self.logger.warning(f"兼容数据库存储失败: {e}")
            
            return {
                'success': True,
                'layers': layers_stored
            }
            
        except Exception as e:
            self.logger.error(f"多层存储失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'layers': layers_stored
            }
    
    def _get_detection_multilayer(self, detection_id: str) -> Optional[Dict]:
        """多层查询检测结果"""
        # Layer 1: 优先从Redis热缓存查询
        if self.redis_client:
            try:
                redis_key = f"detection:{detection_id}"
                redis_data = self.redis_client.get(redis_key)
                
                if redis_data:
                    self.stats['hot_cache_hits'] += 1
                    return json.loads(redis_data)
            except Exception as e:
                self.logger.warning(f"Redis查询失败: {e}")
        
        # Layer 2: 从MongoDB查询
        if self.mongo_db:
            try:
                detections_collection = self.mongo_db['detections']
                result = detections_collection.find_one({'detection_id': detection_id})
                
                if result:
                    self.stats['cold_storage_queries'] += 1
                    # 移除MongoDB的_id字段
                    result.pop('_id', None)
                    return result
            except Exception as e:
                self.logger.warning(f"MongoDB查询失败: {e}")
        
        # Layer 3: 兼容原有数据库
        if self.database:
            try:
                return self.database.get_detection_result(detection_id)
            except Exception as e:
                self.logger.warning(f"兼容数据库查询失败: {e}")
        
        return None
    
    def _get_latest_results(self, limit: int) -> List[Dict]:
        """获取最新检测结果"""
        results = []
        
        # 优先从MongoDB获取最新结果
        if self.mongo_db:
            try:
                detections_collection = self.mongo_db['detections']
                cursor = detections_collection.find().sort('timestamp', -1).limit(limit)
                
                for doc in cursor:
                    doc.pop('_id', None)  # 移除MongoDB的_id字段
                    results.append(doc)
                    
            except Exception as e:
                self.logger.error(f"MongoDB查询最新结果失败: {e}")
        
        # 如果MongoDB没有足够结果，尝试从Redis补充
        if len(results) < limit and self.redis_client:
            try:
                # 获取Redis中的最新检测keys
                redis_keys = self.redis_client.keys('detection:*')
                redis_keys.sort(reverse=True)
                
                for key in redis_keys[:limit - len(results)]:
                    redis_data = self.redis_client.get(key)
                    
                    if redis_data:
                        results.append(json.loads(redis_data))
            except Exception as e:
                self.logger.warning(f"Redis查询最新结果失败: {e}")
        
        # 如果仍不足，尝试从兼容SQLite数据库读取
        if len(results) < limit and self.database:
            try:
                legacy_results = self.database.get_latest_results(limit - len(results))
                # SQLite 返回无 _id 字段
                results.extend(legacy_results)
            except Exception as e:
                self.logger.warning(f"SQLite 查询最新结果失败: {e}")
        
        return results
    
    def _get_stream_results(self, stream_id: str, limit: int, offset: int, 
                           start_time: Optional[float], end_time: Optional[float]) -> List[Dict]:
        """获取指定流的检测结果"""
        results = []
        
        if self.mongo_db:
            try:
                detections_collection = self.mongo_db['detections']
                
                # 构建查询条件
                query = {'stream_id': stream_id}
                
                if start_time or end_time:
                    time_query = {}
                    if start_time:
                        time_query['$gte'] = start_time
                    if end_time:
                        time_query['$lte'] = end_time
                    query['timestamp'] = time_query
                
                # 执行查询
                cursor = detections_collection.find(query).sort('timestamp', -1).skip(offset).limit(limit)
                
                for doc in cursor:
                    doc.pop('_id', None)
                    results.append(doc)
                    
            except Exception as e:
                self.logger.error(f"MongoDB流查询失败: {e}")
        
        # 如果MongoDB未启用，则直接从SQLite查询
        if not results and self.database:
            try:
                all_legacy = self.database.get_latest_results(limit + offset, stream_id)
                # 简易分页
                results = all_legacy[offset:offset+limit]
            except Exception as e:
                self.logger.warning(f"SQLite 流查询失败: {e}")
        
        return results
    
    def _get_summary_statistics(self, period: str) -> Dict:
        """获取汇总统计"""
        stats = {
            'period': period,
            'total_detections': 0,
            'unique_streams': 0,
            'detection_distribution': {},
            'hourly_distribution': {}
        }
        
        # 计算时间范围
        end_time = datetime.utcnow()
        if period == '24h':
            start_time = end_time - timedelta(hours=24)
        elif period == '7d':
            start_time = end_time - timedelta(days=7)
        elif period == '30d':
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(hours=24)
        
        if self.mongo_db:
            try:
                detections_collection = self.mongo_db['detections']
                
                # 总检测数
                total_count = detections_collection.count_documents({
                    'timestamp': {
                        '$gte': start_time.timestamp(),
                        '$lte': end_time.timestamp()
                    }
                })
                stats['total_detections'] = total_count
                
                # 唯一流数
                unique_streams = detections_collection.distinct('stream_id', {
                    'timestamp': {
                        '$gte': start_time.timestamp(),
                        '$lte': end_time.timestamp()
                    }
                })
                stats['unique_streams'] = len(unique_streams)
                
                # 按流分布统计
                pipeline = [
                    {
                        '$match': {
                            'timestamp': {
                                '$gte': start_time.timestamp(),
                                '$lte': end_time.timestamp()
                            }
                        }
                    },
                    {
                        '$group': {
                            '_id': '$stream_id',
                            'count': {'$sum': 1}
                        }
                    }
                ]
                
                for result in detections_collection.aggregate(pipeline):
                    stats['detection_distribution'][result['_id']] = result['count']
                
            except Exception as e:
                self.logger.error(f"统计查询失败: {e}")
        
        return stats
    
    def _get_active_streams(self) -> List[Dict]:
        """获取活跃流列表"""
        streams = []
        
        if self.redis_client:
            try:
                # 从Redis获取最近活跃的流
                stream_keys = self.redis_client.keys('stream:*:latest')
                
                for key in stream_keys:
                    stream_id = key.split(':')[1]
                    last_detection_time = self.redis_client.get(key)
                    
                    if last_detection_time:
                        streams.append({
                            'stream_id': stream_id,
                            'last_detection_time': float(last_detection_time),
                            'status': 'active'
                        })
                        
            except Exception as e:
                self.logger.error(f"获取活跃流失败: {e}")
        
        return sorted(streams, key=lambda x: x['last_detection_time'], reverse=True)
    
    def _start_cleanup_threads(self):
        """启动清理线程"""
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_loop(self):
        """定期清理循环"""
        cleanup_interval = self.config.get('storage', {}).get('cleanup_interval', 3600)
        
        while True:
            try:
                self._cleanup_old_data()
                time.sleep(cleanup_interval)
            except Exception as e:
                self.logger.error(f"清理循环错误: {e}")
                time.sleep(cleanup_interval)
    
    def _cleanup_old_data(self) -> Dict:
        """清理过期数据"""
        cleanup_result = {
            'redis_cleaned': 0,
            'mongodb_cleaned': 0,
            'archive_created': 0
        }
        
        try:
            # MongoDB数据归档
            if self.mongo_db:
                archive_threshold = self.config.get('storage', {}).get('archive_threshold_days', 90)
                archive_time = datetime.utcnow() - timedelta(days=archive_threshold)
                
                detections_collection = self.mongo_db['detections']
                
                # 统计要归档的数据
                archive_count = detections_collection.count_documents({
                    'timestamp': {'$lt': archive_time.timestamp()}
                })
                
                if archive_count > 0:
                    # 可以在这里实现数据归档逻辑
                    # 例如移动到归档集合或对象存储
                    self.logger.info(f"发现 {archive_count} 条需要归档的记录")
                    cleanup_result['archive_created'] = archive_count
            
            self.logger.info(f"数据清理完成: {cleanup_result}")
            
        except Exception as e:
            self.logger.error(f"数据清理失败: {e}")
        
        return cleanup_result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储服务统计信息"""
        storage_usage = 0
        
        # 计算存储使用量
        if self.mongo_db:
            try:
                db_stats = self.mongo_db.command("dbStats")
                storage_usage = db_stats.get('dataSize', 0) / 1024 / 1024  # MB
            except Exception:
                pass
        
        return {
            'service': 'storage',
            'uptime': time.time() - self.stats['start_time'],
            'database_status': {
                'redis_connected': self.redis_client is not None,
                'mongodb_connected': self.mongo_client is not None
            },
            'storage': {
                'total_records': self.stats['total_records'],
                'hot_cache_hits': self.stats['hot_cache_hits'],
                'cold_storage_queries': self.stats['cold_storage_queries'],
                'storage_usage_mb': storage_usage
            },
            'performance': {
                'cache_hit_rate': (
                    self.stats['hot_cache_hits'] / 
                    max(1, self.stats['hot_cache_hits'] + self.stats['cold_storage_queries'])
                ) * 100
            },
            'timestamp': time.time()
        }
    
    def start(self):
        """启动存储服务"""
        server_config = self.config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8083)
        debug = server_config.get('debug', False)
        
        self.logger.info(f"启动数据存储服务 - {host}:{port}")
        self.logger.info(f"Redis状态: {'启用' if self.redis_client else '禁用'}")
        self.logger.info(f"MongoDB状态: {'启用' if self.mongo_client else '禁用'}")
        
        self.app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )

def main():
    """存储服务启动入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据存储服务')
    parser.add_argument('--config', default='config/storage_config.json', help='配置文件路径')
    parser.add_argument('--port', type=int, default=8083, help='服务端口')
    parser.add_argument('--host', default='0.0.0.0', help='服务主机')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    # 创建存储服务实例
    service = StorageService(args.config)
    
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