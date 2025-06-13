import importlib.util
import os
import sys

# Provide dummy modules for optional dependencies
sys.modules.setdefault('cv2', type('cv2', (), {})())
sys.modules.setdefault('shipin', type('shipin', (), {})())

spec = importlib.util.spec_from_file_location(
    'stream_manager',
    os.path.join(os.path.dirname(__file__), '../stream-service/modules/stream_manager.py'),
)
stream_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stream_manager)
StreamManager = stream_manager.StreamManager


def test_risk_level_mapping():
    manager = StreamManager(max_concurrent_streams=1)
    stream_id = manager.add_stream({'name': 'cam1', 'url': 'rtsp://example', 'type': 'rtsp', 'risk_level': '高'})
    stream = manager.get_stream(stream_id)
    assert stream.risk_level == 'high'
