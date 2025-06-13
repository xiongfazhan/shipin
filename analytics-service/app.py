#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动流转分析服务 app.py
- 支持推理服务POST结构化数据
- 自动规则分析（集成 stateful_detection_engine/behavior_model）
- 自动聚合详细推送，支持WebSocket
- 无需人工干预
"""

import os
import time
import json
import logging
from typing import Dict, List, Any, DefaultDict, Optional
from collections import defaultdict, deque
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from datetime import datetime, timedelta
from flask_socketio import SocketIO, emit
import base64
import numpy as np

# 导入分析引擎
from stateful_detection_engine import StatefulDetectionEngine
from behavior_model import AdvancedActionRecognizer

DEFAULT_CONFIG = {
    'server': {'host': '0.0.0.0', 'port': 8086, 'debug': False},
    'services': {'storage_service': 'http://localhost:8083'},
    'aggregation': {'window_seconds': 300},
    'retention_seconds': 3600,
    'websocket': {'enabled': True, 'max_connections': 100, 'cors_origins': '*'},
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("analytics-service")

def img_to_b64(path: str) -> str:
    if not path or not os.path.exists(path): return ''
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.warning(f"图片转码失败: {e}")
        return ''

class AnalyticsService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app = Flask(__name__)
        self._setup_routes()
        self.event_buffer: DefaultDict[str, deque] = defaultdict(deque)
        self.external_webhook_url: Optional[str] = None
        self.scheduler = BackgroundScheduler()
        window = self.config['aggregation']['window_seconds']
        self.scheduler.add_job(self._aggregate_and_push, 'interval', seconds=window, next_run_time=datetime.now() + timedelta(seconds=window))
        self.scheduler.start()

        ws_cfg = self.config.get('websocket', {})
        self.socketio: Optional[SocketIO] = None
        if ws_cfg.get('enabled', False):
            self.socketio = SocketIO(self.app, cors_allowed_origins=ws_cfg.get('cors_origins', '*'), async_mode='threading')
            self._setup_socketio_events()

        self.stateful_engine = StatefulDetectionEngine(r'D:\工创院\后台管理系统\analytics-service\event_rules_config_no_zones.json')
        self.action_recognizer = AdvancedActionRecognizer(r'D:\工创院\后台管理系统\analytics-service\rule_config.yaml')

    def _setup_routes(self):
        @self.app.route('/api/health', methods=['GET'])
        def health():
            return jsonify({'status': 'healthy', 'service': 'analytics'})

        @self.app.route('/api/remote_push/config', methods=['GET', 'POST'])
        def remote_push_config():
            """
            配置或查询远程推送的 Webhook 地址
            GET: 返回当前配置
            POST: 设置新的 Webhook 地址
            """
            if request.method == 'GET':
                return jsonify({
                    'code': 0, 'status': 'ok', 'success': True,
                    'data': {'webhook_url': self.external_webhook_url}
                })

            # POST logic
            data = request.get_json(force=True, silent=True) or {}
            webhook_url = None
            if data and isinstance(data.get('webhooks'), list) and data['webhooks']:
                webhook_url = data['webhooks'][0].get('url')

            if not webhook_url:
                return jsonify({'code': 1, 'status': 'fail', 'message': '请求体中缺少 webhooks[0].url'}), 400

            self.external_webhook_url = webhook_url
            logger.info(f"外部推送 Webhook 地址已更新为: {self.external_webhook_url}")
            return jsonify({
                'code': 0, 'status': 'ok', 'success': True,
                'message': 'Webhook 地址保存成功',
                'data': {'webhook_url': self.external_webhook_url}
            })
        
        @self.app.route('/api/remote_push/test', methods=['POST'])
        def remote_push_test():
            """
            远程推送测试接口
            """
            test_payload = {
                "event_type": "test",
                "message": "这是一条来自 Analytics Service 的测试推送消息。",
                "timestamp": time.time()
            }
            if self.external_webhook_url:
                try:
                    requests.post(self.external_webhook_url, json=test_payload, timeout=5)
                    return jsonify({'code': 0, 'status': 'ok', 'success': True, 'message': '测试推送已发送'})
                except requests.RequestException as e:
                    logger.error(f"测试推送失败: {e}")
                    return jsonify({'code': 1, 'status': 'fail', 'message': f'测试推送失败: {e}'}), 500
            else:
                return jsonify({'code': 1, 'status': 'fail', 'message': '未配置 Webhook 地址，无法测试'}), 400

        @self.app.route('/api/events/detection', methods=['POST'])
        def ingest_detection():
            try:
                data = request.get_json()
                stream_id = data.get('stream_id', 'unknown')
                timestamp = data.get('timestamp', time.time())
                algo_type = data.get('algo_type')

                # === 自动补全/校验动作（如推理端未输出/需复判） ===
                if algo_type == "pose" and ("metrics" not in data or not data["metrics"].get("action")):
                    if "keypoints" in data and data.get("person_id") is not None:
                        try:
                            keypoints = np.array(data['keypoints']).reshape(17, 3)
                            result = self.action_recognizer.recognize_actions_single_person(keypoints, data["person_id"])
                            if result:
                                action, confidence = max(result.items(), key=lambda x: x[1])
                                data["metrics"] = {"action": action, "confidence": confidence}
                        except Exception as ex:
                            logger.warning(f"本地动作补全失败: {ex}")

                # === 写入事件缓存，推送WebSocket ===
                self.event_buffer[stream_id].append(data)
                self._prune_old(stream_id)
                if self.socketio:
                    self._push_to_websocket(data, event_name='detection')

                # === 多帧规则分析自动异常检测 ===
                new_events = []
                try:
                    new_events = self.stateful_engine.process_frame(stream_id, data)
                    for evt in new_events:
                        self.event_buffer[stream_id].append(evt)
                        if self.socketio:
                            self._push_to_websocket(evt, event_name='abnormal')
                except Exception as ex:
                    logger.warning(f"多帧规则分析失败: {ex}")

                logger.info(json.dumps({
                    'event': 'detection_received',
                    'stream_id': stream_id,
                    'timestamp': timestamp,
                    'algo_type': algo_type
                }, ensure_ascii=False))
                return jsonify({'status': 'accepted', 'abnormal_count': len(new_events)})
            except Exception as e:
                logger.error(f"事件接收失败: {e}")
                return jsonify({'error': str(e)}), 400

    def _prune_old(self, stream_id: str):
        retention_seconds = self.config.get('retention_seconds', 3600)
        cutoff = time.time() - retention_seconds
        buf = self.event_buffer[stream_id]
        while buf and buf[0].get('timestamp', 0) < cutoff:
            buf.popleft()
        if not buf:
            del self.event_buffer[stream_id]

    def _aggregate_and_push(self):
        logger.info("开始窗口聚合 …")
        window_sec = self.config['aggregation']['window_seconds']
        now_ts = time.time()
        for stream_id, events in list(self.event_buffer.items()):
            if not events:
                continue
            events_window = [e for e in events if e.get('timestamp', 0) >= now_ts - window_sec]
            if not events_window:
                continue
            summary = self._build_summary(stream_id, events_window)
            self._push_summary(summary)

    def _build_summary(self, stream_id: str, events: List[Dict]) -> Dict:
        window_sec = self.config['aggregation']['window_seconds']
        now_ts = time.time()
        # 目标检测明细
        obj_frames = [e for e in events if e.get('algo_type') == 'object']
        object_detections = []
        for f in obj_frames:
            detection_info = {
                'timestamp': f['timestamp'],
                'objects': f.get('objects') or f.get('detections', []),
                'image': img_to_b64(f.get('frame_path')) if f.get('frame_path') else '',
                'frame_id': f.get('frame_id', None)
            }
            object_detections.append(detection_info)
        abnormal_object_events = [e for e in events if e.get('event_type', '').startswith('目标检测')]
        # 关键点行为明细
        pose_frames = [e for e in events if e.get('algo_type') == 'pose']
        pose_persons = self._aggregate_person_actions(pose_frames)
        abnormal_pose_events = [e for e in events if e.get('event_type', '').startswith('姿态')]

        logger.info(json.dumps({
            'event': 'aggregate_summary',
            'stream_id': stream_id,
            'window_sec': window_sec,
            'object_count': len(object_detections),
            'person_count': len(pose_persons),
            'abnormal_object_events': len(abnormal_object_events),
            'abnormal_pose_events': len(abnormal_pose_events)
        }, ensure_ascii=False))

        return {
            'event_type': 'summary',
            'stream_id': stream_id,
            'window_seconds': window_sec,
            'timestamp': now_ts,
            'object_detections': object_detections,
            'abnormal_object_events': abnormal_object_events,
            'pose_persons': pose_persons,
            'abnormal_pose_events': abnormal_pose_events,
        }

    def _aggregate_person_actions(self, pose_frames: List[Dict]) -> List[Dict]:
        persons = defaultdict(list)
        for frame in pose_frames:
            pid = frame.get('person_id')
            metrics = frame.get('metrics', {})
            action = metrics.get('action')
            confidence = metrics.get('confidence', 1.0)
            if pid is not None and action:
                persons[pid].append({
                    'action': action,
                    'confidence': confidence,
                    'timestamp': frame['timestamp'],
                    'keypoints': frame.get('keypoints')
                })
        # 汇总统计
        result = []
        for pid, actions in persons.items():
            action_summary = defaultdict(list)
            for a in actions:
                action_summary[a['action']].append(a)
            action_detail = [
                {
                    'type': act,
                    'frames': [x['timestamp'] for x in items],
                    'duration': len(items) * 2,  # 2s/帧（按实际采样频率调整）
                    'confidence_avg': sum(x['confidence'] for x in items) / len(items),
                } for act, items in action_summary.items()
            ]
            result.append({'person_id': pid, 'actions': action_detail})
        return result

    def _push_summary(self, summary: Dict):
        try:
            requests.post(f"{self.config['services']['storage_service']}/api/summary", json=summary, timeout=5)
        except Exception as e:
            logger.warning(f"存储服务推送失败: {e}")
        if self.socketio:
            self._push_to_websocket(summary, event_name='summary')

    def _push_to_websocket(self, data, event_name: str = "summary"):
        if self.socketio:
            try:
                self.socketio.emit(event_name, data)
            except Exception as e:
                logger.warning(f"WebSocket 推送异常: {e}")

    def _setup_socketio_events(self):
        @self.socketio.on('connect')
        def handle_connect():
            emit('connect', {'message': 'WebSocket connected'})
        @self.socketio.on('disconnect')
        def handle_disconnect():
            emit('disconnect', {'message': 'WebSocket disconnected'})

    def run(self):
        self.app.run(host=self.config['server']['host'],
                     port=self.config['server']['port'],
                     debug=self.config['server'].get('debug', False))

if __name__ == '__main__':
    service = AnalyticsService(DEFAULT_CONFIG)
    if service.socketio:
        service.socketio.run(service.app, host=DEFAULT_CONFIG['server']['host'], port=DEFAULT_CONFIG['server']['port'])
    else:
        service.run()
