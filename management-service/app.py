#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理平台服务 - Management Service
轻量化的Web管理界面，负责系统编排和配置管理
"""

import os
import sys
import time
import logging
import json
import requests
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from werkzeug.utils import secure_filename

class ManagementService:
    """管理平台服务 - 轻量化设计"""
    
    def __init__(self, config_file: str = 'config/management_config.json'):
        self.config_file = config_file
        self.config = self._load_config()
        
        # 初始化日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Flask应用 - 仅负责前端界面和API编排
        self.app = Flask(__name__, template_folder='templates', static_folder='static')
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
        
        # 服务发现配置
        self.services = {
            'stream': self.config.get('services', {}).get('stream_service', 'http://localhost:8081'),
            'detection': self.config.get('services', {}).get('detection_service', 'http://localhost:8082'),
            'storage': self.config.get('services', {}).get('storage_service', 'http://localhost:8083'),
            'pusher': self.config.get('services', {}).get('pusher_service', 'http://localhost:8086')
        }
        
        self._setup_routes()
        
        # 轻量化统计
        self.stats = {
            'start_time': time.time(),
            'api_calls': 0,
            'active_streams': 0
        }
    
    def _load_config(self) -> Dict:
        """加载轻量化配置"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 8080,
                'debug': False
            },
            'services': {
                'stream_service': 'http://localhost:8081',
                'detection_service': 'http://localhost:8082', 
                'storage_service': 'http://localhost:8083',
                'pusher_service': 'http://localhost:8086'
            },
            'auth': {
                'enabled': False,
                'secret_key': 'management-service-key'
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/management.log'
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
        """设置轻量化日志"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('file', 'logs/management.log')
        
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
        """设置路由 - 专注于前端界面和API编排"""
        
        # 前端页面路由
        @self.app.route('/')
        @self.app.route('/dashboard')
        def dashboard():
            return render_template('dashboard.html', active_page='dashboard')
        
        @self.app.route('/configuration')
        def configuration():
            return render_template('configuration.html', active_page='configuration')
        
        @self.app.route('/streams')
        def streams():
            return render_template('streams.html', active_page='streams')
        
        @self.app.route('/results')
        def results():
            return render_template('results.html', active_page='results')
        
        @self.app.route('/settings')
        def settings_page():
            return render_template('settings.html', active_page='settings')
        
        @self.app.route('/remote_push')
        def remote_push_page():
            return render_template('remote_push.html', active_page='remote_push')
        
        @self.app.route('/summary')
        def summary_results_page():
            return render_template('summary_results.html', active_page='summary')
        
        # 静态文件服务
        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """先尝试本地 static/, 再尝试项目根 static/"""
            local_path = os.path.join('static', filename)
            if os.path.exists(local_path):
                return send_from_directory('static', filename)

            # 回退到全局 static 目录（位于项目根）
            global_static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
            fallback_path = os.path.join(global_static_dir, filename)
            if os.path.exists(fallback_path):
                return send_from_directory(global_static_dir, filename)
            # 仍不存在返回404
            return jsonify({'error': 'File not found'}), 404
        
        # API编排路由 - 转发到对应的微服务
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """轻量化健康检查"""
            return jsonify({
                'status': 'healthy',
                'service': 'management',
                'timestamp': time.time(),
                'uptime': time.time() - self.stats['start_time']
            })
        
        @self.app.route('/api/services/status', methods=['GET'])
        def services_status():
            """检查所有微服务状态"""
            status = {}
            for service_name, service_url in self.services.items():
                try:
                    response = requests.get(f"{service_url}/api/health", timeout=5)
                    status[service_name] = {
                        'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                        'response_time': response.elapsed.total_seconds(),
                        'url': service_url
                    }
                except Exception as e:
                    status[service_name] = {
                        'status': 'offline',
                        'error': str(e),
                        'url': service_url
                    }
            
            return jsonify(status)
        
        # 视频流管理API - 转发到Stream Service
        @self.app.route('/api/streams', methods=['GET'])
        def get_streams():
            """获取视频流列表（带查询参数 & 2 秒缓存）。"""
            # 构造缓存键：查询参数决定不同结果
            cache_key = tuple(sorted(request.args.items()))
            now = time.time()
            # 初始化缓存存储
            if not hasattr(self, '_streams_cache'):
                self._streams_cache = {}

            # 命中缓存且未过期（2 秒）
            entry = self._streams_cache.get(cache_key)
            if entry and (now - entry['ts'] < 2):
                return jsonify(entry['data']), 200

            # 转发请求（附带原查询字符串）
            query_string = request.query_string.decode()
            endpoint = f"/api/streams{'?' + query_string if query_string else ''}"
            resp, status_code = self._proxy_request('stream', endpoint, 'GET')

            # _proxy_request 返回的是 (Response, status_code)
            try:
                data = resp.get_json()
            except Exception:
                data = None

            # 写入缓存
            if status_code == 200 and data is not None:
                self._streams_cache[cache_key] = {'data': data, 'ts': now}

            return resp, status_code
        
        @self.app.route('/api/streams/config', methods=['POST'])
        def upload_stream_config():
            resp, status = self._proxy_request('stream', '/api/streams/config', 'POST', request.json)
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status
        
        @self.app.route('/api/streams/config/upload', methods=['POST'])
        def upload_stream_config_file():
            """代理上传CSV配置文件到stream-service"""
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            # 直接将文件数据代理到stream-service
            # stream-service需要有一个处理文件上传的端点
            service_url = self.services.get('stream')
            if not service_url:
                return jsonify({'error': 'Stream service not configured'}), 503
            
            try:
                # werkzeug.FileStorage object has a 'stream' attribute which is a file-like object
                files = {'file': (file.filename, file.stream, file.mimetype)}
                response = requests.post(f"{service_url}/api/streams/config/upload", files=files, timeout=30)
                
                # 鲁棒的响应处理
                try:
                    response_data = response.json()
                    if response.status_code == 200:
                        self._invalidate_streams_cache()
                    return jsonify(response_data), response.status_code
                except json.JSONDecodeError:
                    self.logger.error(f"stream-service 返回了非JSON响应 (状态码: {response.status_code})。响应内容: {response.text[:500]}")
                    return jsonify({
                        'error': '从流服务收到无效响应',
                        'downstream_status': response.status_code,
                        'downstream_response': response.text[:500]
                    }), 502 # 502 Bad Gateway

            except requests.exceptions.Timeout:
                self.logger.error(f"调用流服务上传文件超时")
                return jsonify({'error': 'stream service timeout'}), 504
            except requests.exceptions.ConnectionError:
                self.logger.error(f"连接流服务上传文件失败")
                return jsonify({'error': 'stream service unavailable'}), 503
            except Exception as e:
                self.logger.error(f"代理文件上传到流服务时出错: {e}")
                return jsonify({'error': f'Internal server error: {str(e)}'}), 500
        
        @self.app.route('/api/streams/<stream_id>/start', methods=['POST'])
        def start_stream(stream_id):
            """启动单个流：透传 frame_config 等自定义字段"""
            payload = request.get_json(silent=True)  # 允许为空
            resp, status = self._proxy_request('stream', f'/api/streams/{stream_id}/start', 'POST', payload)
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status
        
        @self.app.route('/api/streams/<stream_id>/stop', methods=['POST'])
        def stop_stream(stream_id):
            """停止单个流：保持签名一致，向后端透传空 JSON"""
            payload = request.get_json(silent=True)
            resp, status = self._proxy_request('stream', f'/api/streams/{stream_id}/stop', 'POST', payload)
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status
        
        @self.app.route('/api/streams/<stream_id>', methods=['PUT'])
        def update_stream(stream_id):
            """代理更新视频流信息到 stream-service (写入数据库)."""
            resp, status = self._proxy_request('stream', f'/api/streams/{stream_id}/config', 'PUT', request.json)
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status
        
        # 删除视频流
        @self.app.route('/api/streams/<stream_id>', methods=['DELETE'])
        def delete_stream(stream_id):
            resp, status = self._proxy_request('stream', f'/api/streams/{stream_id}', 'DELETE')
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status
        
        # 快照代理 (JPEG)
        @self.app.route('/api/streams/<stream_id>/snapshot')
        def snapshot_proxy(stream_id):
            service_url = self.services.get('stream')
            if not service_url:
                return jsonify({'error': 'stream service not configured'}), 503

            try:
                r = requests.get(f"{service_url}/api/streams/{stream_id}/snapshot", timeout=5)
                return Response(r.content, status=r.status_code, content_type=r.headers.get('Content-Type', 'image/jpeg'))
            except Exception as e:
                self.logger.error(f"快照代理失败: {e}")
                return jsonify({'error': 'snapshot proxy error'}), 502
        
        # 检测结果API - 转发到Storage Service
        @self.app.route('/api/results/latest', methods=['GET'])
        def get_latest_results():
            return self._proxy_request('storage', '/api/results/latest', 'GET')
        
        @self.app.route('/api/results/<stream_id>', methods=['GET'])
        def get_stream_results(stream_id):
            return self._proxy_request('storage', f'/api/results/{stream_id}', 'GET')
        
        # 统计信息API - 聚合多个服务的数据
        @self.app.route('/api/stats', methods=['GET'])
        def get_aggregated_stats():
            """聚合各服务统计信息"""
            aggregated_stats = {
                'management': self.get_stats(),
                'services': {}
            }
            
            for service_name, service_url in self.services.items():
                try:
                    response = requests.get(f"{service_url}/api/stats", timeout=5)
                    if response.status_code == 200:
                        aggregated_stats['services'][service_name] = response.json()
                except Exception as e:
                    aggregated_stats['services'][service_name] = {'error': str(e)}
            
            return jsonify(aggregated_stats)
        
        # 系统状态API
        @self.app.route('/api/system_status', methods=['GET'])
        def get_system_status():
            """获取系统状态信息"""
            return jsonify({
                'success': True,
                'status': 'running',
                'services': self._get_services_health(),
                'timestamp': time.time(),
                'uptime': time.time() - self.stats['start_time']
            })
        
        # 远程推送统计API
        @self.app.route('/api/remote_push/stats', methods=['GET'])
        def get_remote_push_stats():
            """获取远程推送统计信息 - 转发并适配字段"""
            resp, status = self._proxy_request('pusher', '/api/stats', 'GET')
            try:
                data = resp.get_json()
            except Exception:
                return resp, status

            if status == 200 and isinstance(data, dict):
                push_stats = data.get('push_statistics', {})
                perf = data.get('performance', {})
                queue_size = perf.get('queue_size', 0)
                max_size = self.services.get('pusher') and 1000  # default, cannot know exact

                usage_rate = int((queue_size / max(1, max_size)) * 100)

                mapped = {
                    'success': True,
                    'stats': {
                        'total_tasks': push_stats.get('total_pushes', 0),
                        'success_rate': push_stats.get('success_rate', 0),
                        'average_response_time': data.get('performance', {}).get('average_push_time', 0),
                        'total_bytes_sent': 0  # 未统计
                    },
                    'queue_status': {
                        'current_size': queue_size,
                        'max_size': max_size,
                        'usage_rate': usage_rate
                    },
                    'is_enabled': data.get('channels_enabled', {}).get('webhook', True)
                }
                return jsonify(mapped), 200
            return resp, status
        
        @self.app.route('/api/streams/updates')
        def streams_updates_proxy():
            """SSE 代理，转发 stream-service 推送"""
            service_url = self.services.get('stream')
            if not service_url:
                return jsonify({'error': 'stream service not configured'}), 503

            def generate():
                with requests.get(f"{service_url}/api/streams/updates", stream=True) as r:
                    for line in r.iter_lines(decode_unicode=True):
                        if line:
                            yield f"{line}\n"

            return Response(generate(), mimetype='text/event-stream')

        # -------------------------------------------------
        # 兼容旧前端简化接口 (/api/start_stream 等)
        # -------------------------------------------------

        @self.app.route('/api/start_stream', methods=['POST'])
        def start_stream_short():
            # Deprecated: use /api/streams/<id>/start
            return jsonify({'error': 'Deprecated endpoint. Use /api/streams/<id>/start'}), 410

        @self.app.route('/api/stop_stream', methods=['POST'])
        def stop_stream_short():
            # Deprecated: use /api/streams/<stream_id>/stop
            return jsonify({'error': 'Deprecated endpoint. Use /api/streams/<id>/stop'}), 410

        @self.app.route('/api/start_all_streams', methods=['POST'])
        def start_all_streams_short():
            # Deprecated: use /api/streams/start_all
            return jsonify({'error': 'Deprecated endpoint. Use /api/streams/start_all'}), 410

        @self.app.route('/api/stop_all_streams', methods=['POST'])
        def stop_all_streams_short():
            # Deprecated: use /api/streams/stop_all
            return jsonify({'error': 'Deprecated endpoint. Use /api/streams/stop_all'}), 410

        # -----------------------------------------------
        # 前端兼容别名接口 & 辅助统计 (results.js, common.js 等)
        # -----------------------------------------------

        # latest_results -> storage-service /api/results/latest
        @self.app.route('/api/latest_results', methods=['GET'])
        def alias_latest_results():
            return jsonify({'error': 'Deprecated endpoint. Use /api/results/latest'}), 410

        # stream_results/<stream_id> -> storage-service /api/results/<stream_id>
        @self.app.route('/api/stream_results/<stream_id>', methods=['GET'])
        def alias_stream_results(stream_id):
            return jsonify({'error': 'Deprecated endpoint. Use /api/results/<stream_id>'}), 410

        # detection_classes -> 从 storage-service 汇总检测分布
        @self.app.route('/api/detection_classes', methods=['GET'])
        def detection_classes():
            # 调用汇总接口，提取 detection_distribution 的 key
            resp, status = self._proxy_request('storage', '/api/stats/summary', 'GET')
            if status == 200:
                try:
                    data = resp.get_json()
                    classes = sorted(list(data.get('detection_distribution', {}).keys()))
                    return jsonify({'success': True, 'classes': classes})
                except Exception:
                    pass
            # 降级为空列表
            return jsonify({'success': False, 'classes': []}), 200

        # statistics -> storage-service /api/stats/summary
        @self.app.route('/api/statistics', methods=['GET'])
        def statistics_proxy():
            resp, status = self._proxy_request('storage', '/api/stats/summary', 'GET')
            if status == 200:
                data = resp.get_json()
                return jsonify({'success': True, 'statistics': data}), 200
            return resp, status

        # upload_csv (old main.js) -> /api/streams/config/upload，参数名兼容
        @self.app.route('/api/upload_csv', methods=['POST'])
        def upload_csv_alias():
            return jsonify({'error': 'Deprecated endpoint. Use /api/streams/config/upload'}), 410

        # 旧接口 /api/clear_results -> storage-service /api/results/clear（保留兼容）
        @self.app.route('/api/clear_results', methods=['POST'])
        def clear_results_old():
            return jsonify({'error': 'Deprecated endpoint. Use /api/results/clear'}), 410

        # 覆盖 /api/stats 输出，增加 success 字段与常用简易指标
        original_get_stats = get_aggregated_stats  # 捕获闭包内函数
        def wrapped_get_stats():
            inner_resp = original_get_stats()
            data = inner_resp.get_json()
            # 尝试从 storage 和 detection 子统计中提取通用指标
            total_det = 0
            avg_time = 0
            storage = data.get('services', {}).get('storage', {}) if isinstance(data, dict) else {}
            detection = data.get('services', {}).get('detection', {}) if isinstance(data, dict) else {}
            # 不同实现字段名可能不同，做多种尝试
            total_det = storage.get('total_detections') or storage.get('storage', {}).get('total_records', 0)
            avg_time = detection.get('average_processing_time') or detection.get('performance', {}).get('avg_processing_time', 0)
            data.update({
                'success': True,
                'total_detections': total_det,
                'average_processing_time': avg_time
            })
            return jsonify(data)
        # 替换原 route function 的视图 (Flask 允许直接赋值)
        self.app.view_functions[original_get_stats.__name__] = wrapped_get_stats

        # 覆盖 Flask 默认 static 处理函数: 如果请求的是 results/ 开头则从项目根 static 目录读取
        def _patched_static(filename):
            # 若路径以 results/ 开头则转到项目根 static 目录
            if filename.startswith('results/') or filename.startswith('results\\'):
                root_static = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
                return send_from_directory(root_static, filename.replace('\\', '/'))
            # 否则仍走 management-service 本地 static
            return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), filename)

        # 覆盖原来的 static endpoint
        self.app.view_functions['static'] = _patched_static

        # Bulk operations with RESTful paths (new API)
        @self.app.route('/api/streams/start_all', methods=['POST'])
        def start_all_streams():
            payload = request.get_json(force=True) or {}
            resp, status = self._proxy_request('stream', '/api/streams/start_all', 'POST', payload)
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status

        @self.app.route('/api/streams/stop_all', methods=['POST'])
        def stop_all_streams():
            resp, status = self._proxy_request('stream', '/api/streams/stop_all', 'POST')
            if status == 200:
                self._invalidate_streams_cache()
            return resp, status

        # Storage results utilities (new API)
        @self.app.route('/api/results/clear', methods=['POST'])
        def clear_results():
            resp, status = self._proxy_request('storage', '/api/results/clear', 'POST')
            return resp, status

        # Summary / aggregated results (new)
        @self.app.route('/api/results/summary', methods=['GET'])
        def get_summary_results():
            # forward any query params, e.g., ?window=5m
            query_string = request.query_string.decode()
            endpoint = f"/api/results/summary{'?' + query_string if query_string else ''}"
            return self._proxy_request('storage', endpoint, 'GET')

        @self.app.route('/api/remote_push/config', methods=['GET', 'POST'])
        def remote_push_config_proxy():
            method = request.method
            if method == 'GET':
                return self._proxy_request('pusher', '/api/remote_push/config', 'GET')
            else:
                return self._proxy_request('pusher', '/api/remote_push/config', 'POST', request.json)

        @self.app.route('/api/remote_push/test', methods=['POST'])
        def remote_push_test_proxy():
            return self._proxy_request('pusher', '/api/remote_push/test', 'POST', request.json)

        # -----------------------------
        # 统一系统设置（持久化到 config 文件）
        # -----------------------------
        @self.app.route('/api/settings', methods=['GET', 'POST'])
        def system_settings():
            """统一系统设置持久化接口 (仅管理平台本地存储，必要时可广播到其他服务)"""
            if request.method == 'GET':
                # 仅返回管理服务本地 settings 段，避免暴露 service URLs 等敏感信息
                return jsonify({
                    'success': True,
                    'settings': self.config.get('system_settings', {})
                })

            # POST – 保存
            data = request.get_json(force=True) or {}

            # 简单校验
            allowed_keys = {
                'maxStreams', 'detectionConfidence', 'resultRetention',
                'logLevel', 'autoStart', 'saveFrames', 'modelDevice'
            }
            new_settings = {k: v for k, v in data.items() if k in allowed_keys}

            # 合并并写回配置文件
            self.config.setdefault('system_settings', {}).update(new_settings)

            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"写入配置文件失败: {e}")
                return jsonify({'success': False, 'error': '写入配置文件失败'}), 500

            # TODO: 根据需要将部分设置推送到其他微服务 (stream / detection / pusher 等)

            return jsonify({'success': True, 'settings': self.config['system_settings']}), 200

        # 批量导入流配置（JSON）
        @self.app.route('/api/import_streams', methods=['POST'])
        def import_streams_proxy():
            return self._proxy_request('stream', '/api/import_streams', 'POST', request.json)
    
    def _proxy_request(self, service_name: str, endpoint: str, method: str, data: Any = None) -> Dict:
        """API请求代理 - 转发到对应的微服务"""
        self.stats['api_calls'] += 1
        
        service_url = self.services.get(service_name)
        if not service_url:
            return jsonify({'error': f'Service {service_name} not configured'}), 503
        
        try:
            url = f"{service_url}{endpoint}"
            if method == 'GET':
                response = requests.get(url, params=request.args, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=10)
            else:
                return jsonify({'error': f'Unsupported method {method}'}), 400
            
            return jsonify(response.json()), response.status_code
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout calling {service_name} service: {url}")
            return jsonify({'error': f'{service_name} service timeout'}), 504
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error to {service_name} service: {url}")
            return jsonify({'error': f'{service_name} service unavailable'}), 503
        except Exception as e:
            self.logger.error(f"Error calling {service_name} service: {e}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500
    
    def get_stats(self) -> Dict:
        """获取管理服务统计信息"""
        return {
            'service': 'management',
            'uptime': time.time() - self.stats['start_time'],
            'api_calls': self.stats['api_calls'],
            'memory_usage': self._get_memory_usage(),
            'active_services': len([s for s in self.services.keys()]),
            'timestamp': time.time()
        }
    
    def _get_memory_usage(self) -> float:
        """获取内存使用情况"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return 0.0
    
    def _get_services_health(self) -> Dict:
        """获取所有服务的健康状态"""
        health_status = {}
        for service_name, service_url in self.services.items():
            try:
                response = requests.get(f"{service_url}/api/health", timeout=2)
                if response.status_code == 200:
                    health_status[service_name] = 'healthy'
                else:
                    health_status[service_name] = 'unhealthy'
            except Exception:
                health_status[service_name] = 'offline'
        return health_status
    
    def start(self):
        """启动管理服务"""
        server_config = self.config.get('server', {})
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 8080)
        debug = server_config.get('debug', False)
        
        self.logger.info(f"启动管理平台服务 - {host}:{port}")
        self.logger.info(f"服务配置: {self.services}")
        
        self.app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )

    def _invalidate_streams_cache(self):
        """内部工具：写操作成功后清空 streams 缓存"""
        if hasattr(self, '_streams_cache'):
            self._streams_cache.clear()

def main():
    """管理服务启动入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='管理平台服务')
    parser.add_argument('--config', default='config/management_config.json', help='配置文件路径')
    parser.add_argument('--port', type=int, default=8080, help='服务端口')
    parser.add_argument('--host', default='0.0.0.0', help='服务主机')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    # 创建管理服务实例
    service = ManagementService(args.config)
    
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