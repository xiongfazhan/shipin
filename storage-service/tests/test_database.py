import importlib.util
import os
import time

# Load DatabaseManager without installing as a package
spec = importlib.util.spec_from_file_location(
    'database',
    os.path.join(os.path.dirname(__file__), '../modules/database.py'),
)
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)
DatabaseManager = db_module.DatabaseManager


def test_save_and_fetch(tmp_path):
    db_path = tmp_path / 'test.db'
    manager = DatabaseManager(db_path=str(db_path))

    sample = {
        'stream_id': 'cam1',
        'stream_name': 'Camera 1',
        'timestamp': time.time(),
        'processing_time': 0.5,
        'total_objects': 1,
        'detections': [{'class': 'person', 'confidence': 0.9}],
        'frame_shape': [720, 1280, 3],
        'frame_path': None,
    }

    assert manager.save_detection_result(sample) is True

    results = manager.get_latest_results(limit=1, stream_id='cam1')
    assert len(results) == 1
    assert results[0]['stream_id'] == 'cam1'
    assert results[0]['total_objects'] == 1
    assert results[0]['detections'][0]['class'] == 'person'


def test_retrieve_order(tmp_path):
    db_path = tmp_path / 'test.db'
    manager = DatabaseManager(db_path=str(db_path))
    base = time.time()

    for i in range(3):
        sample = {
            'stream_id': 'cam2',
            'stream_name': f'Camera {i}',
            'timestamp': base + i,
            'processing_time': 0.1,
            'total_objects': i,
            'detections': [],
            'frame_shape': None,
            'frame_path': None,
        }
        assert manager.save_detection_result(sample)

    results = manager.get_latest_results(limit=2)
    assert len(results) == 2
    assert results[0]['timestamp'] >= results[1]['timestamp']

