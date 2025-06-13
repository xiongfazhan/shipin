#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频流服务 - Stream Service
负责视频流接入、预过滤抽帧和帧数据管理
"""

import os
import sys
import time
import logging
import json
import threading
import base64
import requests
import csv
import io
import uuid
from typing import Dict, List, Optional, Any
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'filters'))

from modules.stream_manager import StreamManager, StreamStatus
from modules.risk_classifier import RiskConfig, RiskLevel
from filters.frame_filter import get_frame_filter

# 数据持久化
from models import init_engine, Stream  # noqa: E402
from sqlalchemy.orm import Session

class StreamService:
    """视频流服务 - 专注于流管理和预过滤"""
    
    def __init__(self, config_path: str = 'config/stream_config.json'):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        
        # 初始化日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Flask应用
        self.app = Flask(__name__)
        self._setup_routes()
        
        # 核心组件
        self.frame_filter = get_frame_filter()
        self.stream_manager = StreamManager()
        
        # 服务配置
        self.detection_service_url = self.config.get('services', {}).get('detection_service', 'http://localhost:8082')
        self.storage_service_url = self.config.get('services', {}).get('storage_service', 'http://localhost:8083')
        
        # 统计信息
        self.stats = {
            'start_time': time.time(),
            'total_frames_received': 0,
            'total_frames_filtered': 0,
            'total_frames_processed': 0,
            'active_streams': 0
        }
        
        # 线程停止控制事件需在启动任何后台线程前创建
        self.stop_event = threading.Event()

        # 发送线程池，用于并行编解码与HTTP
        send_workers = self.config.get('stream', {}).get('send_workers', 4)
        self.send_executor = ThreadPoolExecutor(max_workers=send_workers)

        # 启动处理线程
        self._start_processing_threads()

        # 初始化数据库
        self.engine, self.Session = init_engine(self.config.get("database", {}).get("path"))

        # 媒体根目录，供本地文件路径补全
        self.media_base_dir = self.config.get('media_dir', os.getcwd())
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8081,
                'debug': False
            },
            'services': {
                'detection_service': 'http://localhost:8082',
                'storage_service': 'http://localhost:8083'
            },
            'stream': {
                'max_concurrent_streams': 20,
                'frame_buffer_size': 100,
                'default_frame_interval': 2.0
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/stream.log'
            }
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
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
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        return default_config
    
    def _setup_logging(self):
        """设置日志系统"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('file', 'logs/stream.log')
        
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
    
    def _setup_routes(self):
        """设置API路由"""
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """健康检查"""
            return jsonify({
                'status': 'healthy',
                'service': 'stream',
                'timestamp': time.time(),
                'uptime': time.time() - self.stats['start_time'],
                'active_streams': self.stats['active_streams']
            })
        
        @self.app.route('/api/streams', methods=['GET'])
        def get_streams():
            """获取视频流列表 (分页 & 运行状态)"""
            offset = int(request.args.get('offset', 0))
            limit = int(request.args.get('limit', 100))

            session: Session = self.Session()
            try:
                total = session.query(Stream).count()
                db_streams = (
                    session.query(Stream)
                    .order_by(Stream.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                streams_list = []
                for db_stream in db_streams:
                    stream_id = db_stream.stream_id
                    runtime_info = self.stream_manager.get_stream(stream_id)

                    is_running = False
                    status_value = 'stopped'
                    if runtime_info:
                        is_running = runtime_info.status == StreamStatus.RUNNING
                        status_value = runtime_info.status.value

                    streams_list.append({
                        **db_stream.as_dict(),
                        'is_running': is_running,
                        'status': status_value,
                        'filter_stats': self.frame_filter.get_stream_stats(stream_id),
                    })

                return jsonify({
                    'success': True,
                    'streams': streams_list,
                    'total': total,
                    'offset': offset,
                    'limit': limit
                })
            finally:
                session.close()
        
        @self.app.route('/api/streams/config', methods=['POST'])
        def upload_stream_config():
            """上传流配置"""
            try:
                data = request.get_json()
                
                if 'streams' in data:
                    # 批量配置
                    for stream_config in data['streams']:
                        self._configure_single_stream(stream_config)
                    return jsonify({'status': 'success', 'message': f'配置了 {len(data["streams"])} 个流'})
                else:
                    # 单个流配置
                    self._configure_single_stream(data)
                    return jsonify({'status': 'success', 'message': '流配置成功'})
                    
            except Exception as e:
                self.logger.error(f"配置流失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/streams/config/upload', methods=['POST'])
        def upload_stream_config_file():
            """通过上传CSV文件批量配置流"""
            if 'file' not in request.files:
                return jsonify({'error': 'No file part in the request'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'No file selected for uploading'}), 400
            
            if file and file.filename.endswith('.csv'):
                try:
                    # 将文件流解码为文本
                    stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
                    csv_reader = csv.DictReader(stream)
                    
                    added_count = 0
                    for row in csv_reader:
                        # 清理可能的空值
                        stream_config = {k: v for k, v in row.items() if v is not None and v != ''}
                        if 'url' in stream_config and 'name' in stream_config:
                            self._configure_single_stream(stream_config)
                            added_count += 1
                    
                    self.logger.info(f"通过CSV成功配置了 {added_count} 个流")
                    return jsonify({
                        'success': True, 
                        'message': f'成功添加 {added_count} 个视频流配置',
                        'added_count': added_count
                    })

                except Exception as e:
                    self.logger.error(f"处理CSV文件失败: {e}", exc_info=True)
                    return jsonify({'error': 'Failed to process CSV file', 'details': str(e)}), 500
            else:
                return jsonify({'error': 'Unsupported file type, please upload a CSV file'}), 400
        
        @self.app.route('/api/streams/<stream_id>/start', methods=['POST'])
        def start_stream(stream_id):
            """启动视频流，可携带 frame_config 指定自定义抽帧间隔"""
            try:
                payload = request.get_json(silent=True) or {}
                frame_cfg = payload.get('frame_config') or {}

                # 支持两种格式：{frameInterval: 0.5} 或 {frame_interval: 0.5}
                override_interval = (
                    frame_cfg.get('frameInterval')
                    or frame_cfg.get('frame_interval')
                )

                result = self._start_single_stream(stream_id, override_interval)
                if result['success']:
                    return jsonify({'status': 'success', 'message': f'流 {stream_id} 启动成功'})
                else:
                    return jsonify({'status': 'error', 'message': result['error']}), 400
            except Exception as e:
                self.logger.error(f"启动流 {stream_id} 失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/streams/<stream_id>/stop', methods=['POST'])
        def stop_stream(stream_id):
            """停止视频流"""
            try:
                result = self._stop_single_stream(stream_id)
                if result['success']:
                    return jsonify({'status': 'success', 'message': f'流 {stream_id} 停止成功'})
                else:
                    return jsonify({'status': 'error', 'message': result['error']}), 400
            except Exception as e:
                self.logger.error(f"停止流 {stream_id} 失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/streams/<stream_id>/config', methods=['PUT'])
        def update_stream_config(stream_id):
            """更新流配置"""
            try:
                raw_data = request.get_json(force=True) or {}

                # 兼容两种格式：{config:{...}} 或直接字段
                config = raw_data.get('config') if 'config' in raw_data and isinstance(raw_data['config'], dict) else raw_data

                # -------- 规范 risk_level 字段并补全间隔 --------
                if config and 'risk_level' in config:
                    rl_map = {
                        '高': 'HIGH', '中': 'MEDIUM', '低': 'LOW',
                        'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW'
                    }
                    orig_rl = str(config['risk_level']).strip()
                    config['risk_level'] = rl_map.get(orig_rl, orig_rl.upper())

                # 若未显式提供 frame_interval，根据风险等级默认值补全
                if config and 'frame_interval' not in config and 'risk_level' in config:
                    lvl = str(config['risk_level']).upper()
                    config['frame_interval'] = self.frame_filter.risk_intervals.get(lvl, 2.0)

                # 更新过滤器配置
                if config:
                    self.frame_filter.configure_stream(stream_id, config)

                # 更新流管理器配置（兼容旧实例无 config 属性）
                if stream_id in self.stream_manager.streams and config:
                    stream_obj = self.stream_manager.streams[stream_id]
                    if not hasattr(stream_obj, 'config') or stream_obj.config is None:
                        stream_obj.config = {}
                    if isinstance(stream_obj.config, dict):
                        stream_obj.config.update(config)
                    # 同时同步基本字段，例如 risk_level / name / interval
                    self.stream_manager.update_stream_config(stream_id, config)

                # 更新数据库
                session: Session = self.Session()
                try:
                    db_stream = session.query(Stream).filter_by(stream_id=stream_id).first()
                    if db_stream:
                        for k, v in config.items():
                            if hasattr(db_stream, k):
                                setattr(db_stream, k, v)
                        session.commit()
                finally:
                    session.close()
                
                return jsonify({'status': 'success', 'message': f'流 {stream_id} 配置更新成功'})
                
            except Exception as e:
                self.logger.error(f"更新流配置失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/streams/<stream_id>/stats', methods=['GET'])
        def get_stream_stats(stream_id):
            """获取流统计信息"""
            try:
                filter_stats = self.frame_filter.get_stream_stats(stream_id)
                stream_info = self.stream_manager.streams.get(stream_id, {})
                
                stats = {
                    'stream_id': stream_id,
                    'filter_stats': filter_stats,
                    'stream_info': {
                        'name': stream_info.name,
                        'status': stream_info.status,
                        'url': stream_info.url
                    }
                }
                
                return jsonify(stats)
                
            except Exception as e:
                self.logger.error(f"获取流统计失败: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/stats', methods=['GET'])
        def get_api_stats():
            """获取服务统计信息"""
            return jsonify(self.get_stats())
        
        @self.app.route('/api/filter/config', methods=['GET', 'POST'])
        def manage_filter_config():
            """管理过滤器配置"""
            if request.method == 'GET':
                return jsonify({
                    'risk_intervals': self.frame_filter.get_risk_intervals(),
                    'all_stats': self.frame_filter.get_all_stats()
                })
            else:
                try:
                    config = request.get_json()
                    # 更新风险等级配置
                    if 'risk_intervals' in config:
                        self.frame_filter.risk_intervals.update(config['risk_intervals'])
                    
                    return jsonify({'status': 'success', 'message': '过滤器配置更新成功'})
                except Exception as e:
                    return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/streams/updates')
        def stream_updates():
            """Server-Sent Events: 推送流状态变更，每 1 秒。"""

            def event_stream():
                last_snapshot = {}
                while True:
                    # 构建当前快照
                    current = {}
                    for stream_id, stream_info in self.stream_manager.streams.items():
                        current[stream_id] = 'running' if stream_info.status.value == 'running' else 'stopped'

                    # 对比差异
                    changed = {
                        sid: state for sid, state in current.items()
                        if last_snapshot.get(sid) != state
                    }
                    if changed:
                        yield f'data: {json.dumps(changed, ensure_ascii=False)}\n\n'
                        last_snapshot = current.copy()
                    time.sleep(1)

            return Response(event_stream(), mimetype='text/event-stream')

        # 获取最新帧快照（JPEG）
        @self.app.route('/api/streams/<stream_id>/snapshot', methods=['GET'])
        def snapshot_stream(stream_id):
            """返回指定流最近一帧 JPEG，用于前端预览"""
            # 先尝试从正在运行的流缓冲区读取
            stream_info = self.stream_manager.get_stream(stream_id)

            frame = None
            if stream_info and stream_info.capture:
                frame = self.stream_manager.get_frame_from_buffer(stream_id)
                if frame is None:
                    ret, cap_frame = stream_info.capture.read()
                    if ret:
                        frame = cap_frame

            # 若流未运行或仍无帧，则临时打开一次 VideoCapture
            if frame is None:
                # 从数据库读取 URL
                session: Session = self.Session()
                try:
                    db_stream = session.query(Stream).filter_by(stream_id=stream_id).first()
                    if not db_stream:
                        # 兼容前端使用 name 作为 id 的情况
                        db_stream = session.query(Stream).filter_by(name=stream_id).first()
                    if not db_stream:
                        return jsonify({'error': 'stream not found'}), 404
                    stream_url = db_stream.url
                finally:
                    session.close()

                try:
                    import cv2
                    # 若为本地文件，解析绝对路径
                    stream_url = self._resolve_media_path(stream_url)
                    cap = cv2.VideoCapture(stream_url)
                    ret, cap_frame = cap.read()
                    cap.release()
                    if ret:
                        frame = cap_frame
                except Exception as e:
                    self.logger.error(f'临时抓帧失败: {e}')

            if frame is None:
                return jsonify({'error': 'no frame available'}), 404

            try:
                _, buf = cv2.imencode('.jpg', frame)
                return Response(buf.tobytes(), mimetype='image/jpeg')
            except Exception as e:
                self.logger.error(f'编码快照失败: {e}')
                return jsonify({'error': 'encode error'}), 500

        # 删除流配置
        @self.app.route('/api/streams/<stream_id>', methods=['DELETE'])
        def delete_stream(stream_id):
            """停止并删除流配置（数据库+运行时）"""
            # 停止运行中的流
            self._stop_single_stream(stream_id)

            # 从数据库删除
            session: Session = self.Session()
            try:
                db_stream = session.query(Stream).filter_by(stream_id=stream_id).first()
                if db_stream:
                    session.delete(db_stream)
                    session.commit()
            finally:
                session.close()

            # 清理缓存/内存
            if stream_id in self.stream_manager.streams:
                del self.stream_manager.streams[stream_id]

            return jsonify({'success': True, 'message': 'stream deleted'})

        # ------------------------------
        # 批量控制端点，供管理平台调用
        # ------------------------------

        @self.app.route('/api/streams/start_all', methods=['POST'])
        def start_all_streams():
            """批量启动所有流，可通过 frame_config 调整全局风险等级间隔"""
            payload = request.get_json(silent=True) or {}
            frame_cfg = payload.get('frame_config') or {}

            # 如果提供了高/中/低风险间隔则更新全局 risk_intervals
            key_map = {
                'highRiskInterval': 'HIGH',
                'mediumRiskInterval': 'MEDIUM',
                'lowRiskInterval': 'LOW'
            }
            updated = False
            for k, level in key_map.items():
                if k in frame_cfg:
                    try:
                        self.frame_filter.risk_intervals[level] = float(frame_cfg[k])
                        updated = True
                    except ValueError:
                        pass
            if updated:
                self.logger.info(f"批量启动更新 risk_intervals 为: {self.frame_filter.risk_intervals}")

            started = 0
            errors = {}
            session: Session = self.Session()
            try:
                all_db_streams = session.query(Stream).all()
                for db_stream in all_db_streams:
                    sid = db_stream.stream_id
                    if self.stream_manager.get_stream(sid) and self.stream_manager.get_stream(sid).is_running():
                        continue  # 已运行
                    # 根据流风险等级确定间隔
                    override_interval = None
                    level = str(db_stream.risk_level or '').lower()
                    if level in ['高', 'high'] and 'highRiskInterval' in frame_cfg:
                        override_interval = frame_cfg['highRiskInterval']
                    elif level in ['中', 'medium'] and 'mediumRiskInterval' in frame_cfg:
                        override_interval = frame_cfg['mediumRiskInterval']
                    elif level in ['低', 'low'] and 'lowRiskInterval' in frame_cfg:
                        override_interval = frame_cfg['lowRiskInterval']

                    result = self._start_single_stream(sid, override_interval)
                    if result.get('success'):
                        started += 1
                    else:
                        errors[sid] = result.get('error', 'unknown')
                msg = f"成功启动 {started} 路视频流"
                return jsonify({'success': True, 'message': msg, 'errors': errors})
            finally:
                session.close()

        @self.app.route('/api/streams/stop_all', methods=['POST'])
        def stop_all_streams():
            """停止所有正在运行的流"""
            stopped = 0
            errors = {}
            for sid, sinfo in list(self.stream_manager.streams.items()):
                if not sinfo.is_running():
                    continue
                result = self._stop_single_stream(sid)
                if result.get('success'):
                    stopped += 1
                else:
                    errors[sid] = result.get('error', 'unknown')
            msg = f"成功停止 {stopped} 路视频流"
            return jsonify({'success': True, 'message': msg, 'errors': errors})

        @self.app.route('/api/streams/clear', methods=['POST'])
        def clear_all_streams():
            """停止并删除所有流配置（包括数据库与内存）"""
            try:
                # 统计停止数量
                stopped = 0
                for sid in list(self.stream_manager.streams.keys()):
                    try:
                        self._stop_single_stream(sid)
                    except Exception:
                        pass
                    # 移除过滤器缓存
                    try:
                        self.frame_filter.remove_stream(sid)
                    except Exception:
                        pass
                    stopped += 1
                # 清空管理器内部状态
                self.stream_manager.streams.clear()
                self.stream_manager.workers.clear()

                # 清空数据库
                session: Session = self.Session()
                try:
                    deleted = session.query(Stream).delete()
                    session.commit()
                finally:
                    session.close()

                return jsonify({'success': True, 'stopped': stopped, 'deleted': deleted}), 200
            except Exception as e:
                self.logger.error(f"清空流配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/import_streams', methods=['POST'])
        def import_streams():
            """批量导入流配置（JSON 格式）"""
            try:
                data = request.get_json(force=True) or {}
                streams_list = data.get('streams')
                if not streams_list or not isinstance(streams_list, list):
                    return jsonify({'success': False, 'error': 'Missing "streams" list'}), 400

                added = 0
                errors = []
                for cfg in streams_list:
                    try:
                        self._configure_single_stream(cfg)
                        added += 1
                    except Exception as e:
                        errors.append({'stream': cfg.get('stream_id') or cfg.get('name'), 'error': str(e)})

                return jsonify({'success': True, 'added_count': added, 'errors': errors}), 200
            except Exception as e:
                self.logger.error(f"导入流配置失败: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def _configure_single_stream(self, stream_config: Dict[str, Any]):
        """将配置持久化到数据库 (UPSERT)."""
        if 'stream_id' not in stream_config or not stream_config['stream_id']:
            stream_config['stream_id'] = str(uuid.uuid4())

        stream_id = stream_config['stream_id']

        # -------- 规范 risk_level 并补全 interval --------
        rl_map = {
            '高': 'HIGH', '中': 'MEDIUM', '低': 'LOW',
            'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW'
        }
        rl_val = stream_config.get('risk_level')
        if rl_val is not None:
            stream_config['risk_level'] = rl_map.get(str(rl_val).strip(), str(rl_val).upper())

        # 根据风险等级自动补全 interval，如果未提供
        if 'interval' not in stream_config and 'risk_level' in stream_config:
            lvl = str(stream_config['risk_level']).upper()
            stream_config['interval'] = self.frame_filter.risk_intervals.get(lvl, 2.0)

        self.logger.info(f"持久化流配置: {stream_id}")

        session: Session = self.Session()
        try:
            existing = session.query(Stream).filter_by(stream_id=stream_id).first()

            # 映射字段到模型
            mapped_fields = {
                'stream_id': stream_config.get('stream_id'),
                'name': stream_config.get('name'),
                'url': stream_config.get('url'),
                'risk_level': stream_config.get('risk_level', '中'),
                'description': stream_config.get('description'),
                'type': stream_config.get('type'),
                'push_endpoint': stream_config.get('push_endpoint'),
                'push_type': stream_config.get('push_type'),
                'push_port': (
                    int(str(stream_config.get('push_port', '')).strip())
                    if str(stream_config.get('push_port', '')).strip().isdigit()
                    else None
                ),
            }

            if existing:
                for k, v in mapped_fields.items():
                    if v is not None:
                        setattr(existing, k, v)
            else:
                new_stream = Stream(**mapped_fields)
                session.add(new_stream)

            session.commit()
        finally:
            session.close()
    
    def _start_single_stream(self, stream_id: str, override_interval: float = None) -> Dict[str, Any]:
        """启动单个视频流进程"""
        try:
            # 如果流在运行时尚未加载，则从数据库载入配置
            if not self.stream_manager.get_stream(stream_id):
                session: Session = self.Session()
                try:
                    db_stream = session.query(Stream).filter_by(stream_id=stream_id).first()
                    if not db_stream:
                        # 兼容前端使用 name 作为 id 的情况
                        db_stream = session.query(Stream).filter_by(name=stream_id).first()
                    if not db_stream:
                        return {'success': False, 'error': '未找到流配置'}

                    stream_dict = db_stream.as_dict()
                    # 若为本地文件流，解析绝对路径
                    if db_stream.type == 'file':
                        stream_dict['url'] = self._resolve_media_path(stream_dict['url'])

                    # 根据风险等级或覆盖值确定帧间隔
                    if override_interval is not None:
                        stream_dict['interval'] = float(override_interval)
                    else:
                        rl_val = stream_dict.get('risk_level', 'MEDIUM')
                        rl_map = {
                            '高': 'HIGH', '中': 'MEDIUM', '低': 'LOW',
                            'high': 'HIGH', 'medium': 'MEDIUM', 'low': 'LOW',
                            'HIGH': 'HIGH', 'MEDIUM': 'MEDIUM', 'LOW': 'LOW'
                        }
                        risk_level_key = rl_map.get(str(rl_val).strip(), str(rl_val).upper())
                        stream_dict['risk_level'] = risk_level_key  # 规范化存回
                        stream_dict['interval'] = self.frame_filter.risk_intervals.get(risk_level_key, 2.0)

                    self.stream_manager.add_stream(stream_dict)

                    # 配置过滤器（使用 stream_dict['interval']）
                    risk_cfg = RiskConfig(
                        level=stream_dict.get('risk_level', 'medium'),
                        frame_interval=stream_dict.get('interval', 1.0),
                        confidence_threshold=stream_dict.get('confidence_threshold', 0.5),
                        max_objects=stream_dict.get('max_objects', 10),
                        detection_classes=stream_dict.get('detection_classes'),
                    )
                    self.frame_filter.configure_stream(stream_id, asdict(risk_cfg))
                finally:
                    session.close()

            # 如果流已存在于管理器中，则可能需要更新间隔
            if override_interval is not None and self.stream_manager.get_stream(stream_id):
                self.stream_manager.update_stream_config(stream_id, {'interval': float(override_interval)})
                # 同时更新过滤器
                cfg = self.frame_filter.get_stream_config(stream_id)
                cfg['frame_interval'] = float(override_interval)
                self.frame_filter.configure_stream(stream_id, cfg)

            success = self.stream_manager.start_stream(stream_id)
            if success:
                self.stats['active_streams'] += 1
                return {'success': True}
            else:
                return {'success': False, 'error': '流启动失败'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _stop_single_stream(self, stream_id: str) -> Dict[str, Any]:
        """停止单个流"""
        try:
            # 停止流管理器中的流
            success = self.stream_manager.stop_stream(stream_id)
            if success:
                self.stats['active_streams'] = max(0, self.stats['active_streams'] - 1)
                return {'success': True}
            else:
                return {'success': False, 'error': '流停止失败'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _start_processing_threads(self):
        """启动处理线程"""
        # 帧处理线程
        self.frame_processing_thread = threading.Thread(
            target=self._frame_processing_loop, daemon=True
        )
        self.frame_processing_thread.start()
        
        # 统计更新线程
        self.stats_thread = threading.Thread(
            target=self._stats_update_loop, daemon=True
        )
        self.stats_thread.start()
    
    def _frame_processing_loop(self):
        """核心处理循环 - 从缓冲区获取帧并发送到检测服务"""
        while not self.stop_event.is_set():
            try:
                # 从所有运行中的流中轮流获取帧
                active_streams_items = self.stream_manager.get_running_streams()
                
                if not active_streams_items:
                    time.sleep(0.5)
                    continue

                for stream_id, stream_info in active_streams_items:
                    # 使用属性访问
                    if not stream_info.is_running():
                        continue
                    
                    # 根据最后一次发送的时间决定是否发送，避免被读取频率影响
                    last_sent = getattr(stream_info, "_last_sent_ts", 0)
                    if time.time() - last_sent < stream_info.interval:
                        continue
                        
                    frame = self.stream_manager.get_frame_from_buffer(stream_id)
                    if frame is not None:
                        self.stats['total_frames_received'] += 1
                        
                        # 直接异步提交到线程池，节流逻辑由 _last_sent_ts 控制
                        self.send_executor.submit(
                            self._send_to_detection_service,
                            {
                                'stream_id': stream_id,
                                'frame': frame,
                                'timestamp': time.time(),
                                'risk_config': self.frame_filter.get_stream_config(stream_id)
                            }
                        )
                        # 记录本次发送时间
                        stream_info._last_sent_ts = time.time()
                
                # 避免CPU空转
                time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"帧处理循环错误: {e}", exc_info=True)
                time.sleep(1) # 发生错误时暂停一下
    
    def _capture_frame_from_stream(self, stream_id: str, stream_info: Any) -> Optional[Dict[str, Any]]:
        """从单个视频流捕获帧"""
        try:
            # stream_info 现在是 StreamInfo 对象
            if not stream_info.is_running() or not stream_info.capture:
                return None
            
            ret, frame = stream_info.capture.read()
            if not ret:
                stream_info.error_count += 1
                if stream_info.error_count > 100: # 连续100次失败则停止
                    self.logger.warning(f"流 {stream_id} 连续读取失败，将停止该流")
                    self._stop_single_stream(stream_id)
                return None
            
            stream_info.error_count = 0
            return frame

        except Exception as e:
            self.logger.error(f"捕获流 {stream_id} 的帧时出错: {e}")
            stream_info.error_count += 1
            return None
    
    def _send_to_detection_service(self, frame_data: Dict[str, Any]):
        """将帧数据异步发送到检测服务"""
        try:
            # 编码帧数据
            frame = frame_data['frame']
            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 构建请求数据
            payload = {
                'stream_id': frame_data['stream_id'],
                'image': frame_base64,
                'timestamp': frame_data['timestamp'],
                'config': frame_data.get('risk_config', {})
            }
            
            # 异步发送到检测服务
            response = requests.post(
                f"{self.detection_service_url}/api/detect/frame",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                self.stats['total_frames_processed'] += 1
                self.logger.info(f"帧发送成功: {frame_data['stream_id']}")
            else:
                self.logger.warning(f"检测服务响应错误: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"发送到检测服务失败: {e}")
    
    def _stats_update_loop(self):
        """定期更新统计信息"""
        while not self.stop_event.is_set():
            try:
                self.stats['active_streams'] = self.stream_manager.get_active_stream_count()
                
                # 更新每个流的状态
                for stream_info in self.stream_manager.streams.values():
                    if stream_info.process and stream_info.process.is_alive():
                        stream_info.status = 'running'
                    else:
                        if stream_info.status == 'running':
                            stream_info.status = 'stopped' # 如果进程不在了，更新状态
                
                time.sleep(5) # 每5秒更新一次
            except Exception as e:
                self.logger.error(f"统计更新错误: {e}", exc_info=True)
                time.sleep(5)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取当前服务的统计信息"""
        filter_stats = self.frame_filter.get_all_stats()
        
        # 生成每个流的健康信息
        per_stream = {}
        for sid, sinfo in self.stream_manager.streams.items():
            per_stream[sid] = {
                'status': sinfo.status.value,
                'last_sent_ts': getattr(sinfo, '_last_sent_ts', None),
                'time_since_last_sent': (
                    time.time() - getattr(sinfo, '_last_sent_ts', 0)
                    if getattr(sinfo, '_last_sent_ts', None) else None
                ),
                'last_frame_time': sinfo.last_frame_time,
                'time_since_last_read': (
                    time.time() - sinfo.last_frame_time if sinfo.last_frame_time else None
                ),
            }

        return {
            'service': 'stream',
            'uptime': time.time() - self.stats['start_time'],
            'frames': {
                'total_received': self.stats['total_frames_received'],
                'total_filtered': self.stats['total_frames_filtered'],
                'total_processed': self.stats['total_frames_processed'],
                'filter_efficiency': (
                    self.stats['total_frames_filtered'] / max(1, self.stats['total_frames_received'])
                ) * 100
            },
            'streams': {
                'active': self.stats['active_streams'],
                'total_configured': filter_stats['total_streams'],
                'details': per_stream
            },
            'filter_stats': filter_stats,
            'timestamp': time.time()
        }
    
    def start(self):
        """启动视频流服务"""
        server_config = self.config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8081)
        debug = server_config.get('debug', False)
        
        self.logger.info(f"启动视频流服务 - {host}:{port}")
        self.logger.info(f"检测服务URL: {self.detection_service_url}")
        self.logger.info(f"存储服务URL: {self.storage_service_url}")
        
        self.app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )

    def _resolve_media_path(self, path: str) -> str:
        """将相对路径转换为绝对媒体路径"""
        if '://' in path or os.path.isabs(path):
            return path
        return os.path.join(self.media_base_dir, path)

def main():
    """视频流服务启动入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='视频流服务')
    parser.add_argument('--config', default='config/stream_config.json', help='配置文件路径')
    parser.add_argument('--port', type=int, default=8081, help='服务端口')
    parser.add_argument('--host', default='0.0.0.0', help='服务主机')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    # 创建视频流服务实例
    service = StreamService(args.config)
    
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