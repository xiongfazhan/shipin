# 集成服务健康检查，确保各微服务的基本接口可用
import importlib.util
import sys


def test_analytics_service_health():
    import os
    sys.path.insert(0, os.path.abspath("analytics-service"))
    sys.modules.setdefault('cv2', type('cv2', (), {})())
    sys.modules.setdefault('flask_socketio', type('flask_socketio', (), {'SocketIO': lambda *a, **k: type('SO', (), {'emit': lambda *a, **k: None})(), 'emit': lambda *a, **k: None}))

    class DummyScheduler:
        def add_job(self, *a, **k):
            pass
        def start(self):
            pass

    spec = importlib.util.spec_from_file_location('analytics_app', 'analytics-service/app.py')
    analytics_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analytics_app)
    analytics_app.BackgroundScheduler = DummyScheduler

    config = dict(analytics_app.DEFAULT_CONFIG)
    config["websocket"] = {"enabled": False}
    service = analytics_app.AnalyticsService(config)
    client = service.app.test_client()
    resp = client.get('/api/health')
    assert resp.json['status'] == 'healthy'


def test_detection_service_health():
    import os
    sys.path.insert(0, os.path.abspath("detection-service"))
    sys.modules.setdefault('cv2', type('cv2', (), {'imdecode': lambda *a, **k: None, 'imencode': lambda *a, **k: None})())
    sys.modules.setdefault('torch', type('torch', (), {'cuda': type('cuda', (), {'is_available': lambda: False})})())
    sys.modules.setdefault('ultralytics', type('ultralytics', (), {'YOLO': lambda *a, **k: type('Y', (), {'predict': lambda *a, **k: []})()})())

    spec = importlib.util.spec_from_file_location('detect_app', 'detection-service/app.py')
    detect_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detect_app)

    service = detect_app.DetectionService()
    client = service.app.test_client()
    resp = client.get('/api/health')
    assert resp.json['status'] == 'healthy'


def test_storage_service_health():
    import os
    sys.path.insert(0, os.path.abspath("storage-service"))
    sys.modules.setdefault('redis', type('redis', (), {'Redis': lambda *a, **k: type('R', (), {'ping': lambda self: None})()}))
    sys.modules.setdefault('pymongo', type('pymongo', (), {'MongoClient': lambda *a, **k: type('M', (), {'admin': type('A', (), {'command': lambda self, cmd: None})(), '__getitem__': lambda self, name: type('DB', (), {'__getitem__': lambda self, n: type('C', (), {'create_index': lambda *a, **k: None, 'count_documents': lambda *a, **k: 0})()})()})(), 'errors': type('E', (), {})}))

    spec = importlib.util.spec_from_file_location('storage_app', 'storage-service/app.py')
    storage_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(storage_app)

    service = storage_app.StorageService()
    client = service.app.test_client()
    resp = client.get('/api/health')
    assert resp.json['status'] == 'healthy'


def test_stream_service_health():
    import os
    sys.path.insert(0, os.path.abspath("stream-service"))
    sys.modules.setdefault('cv2', type('cv2', (), {'VideoCapture': lambda *a, **k: type('Cap', (), {'read': lambda self: (False, None), 'release': lambda self: None})(), 'imencode': lambda *a, **k: (True, b'')})())
    sys.modules.setdefault('requests', type('requests', (), {'post': lambda *a, **k: None, 'get': lambda *a, **k: type('Resp', (), {'content': b'', 'status_code': 200, 'headers': {'Content-Type': 'image/jpeg'}})()}))

    spec = importlib.util.spec_from_file_location('stream_app', 'stream-service/app.py')
    stream_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stream_app)

    service = stream_app.StreamService()
    client = service.app.test_client()
    resp = client.get('/api/health')
    assert resp.json['status'] == 'healthy'
