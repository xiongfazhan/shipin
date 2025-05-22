import unittest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.database.database_setup import init_db
from src.database.models import Base, VideoConfiguration, DetectionResult
from src.database import crud

class TestDatabaseCrud(unittest.TestCase):

    engine = None
    session = None

    @classmethod
    def setUpClass(cls):
        """Set up an in-memory SQLite database for all tests in this class."""
        cls.engine = create_engine('sqlite:///:memory:')
        init_db(cls.engine) # Pass engine to init_db to use in-memory DB

        # Populate with some test data
        cls.session = Session(bind=cls.engine)
        
        # Video Configs
        vc1 = VideoConfiguration(id=1, video_path="/test/vid1.mp4", video_name="Video 1", priority=1, enabled=True, processing_status="completed")
        vc2 = VideoConfiguration(id=2, video_path="/test/vid2.mp4", video_name="Video 2", priority=2, enabled=True, processing_status="pending")
        cls.session.add_all([vc1, vc2])
        cls.session.commit()

        # Detections for Video 1
        det1_v1_f0 = DetectionResult(video_configuration_id=1, frame_number=0, class_name="person", confidence=0.9, x1=10,y1=10,x2=60,y2=110)
        det2_v1_f0 = DetectionResult(video_configuration_id=1, frame_number=0, class_name="car", confidence=0.8, x1=70,y1=50,x2=170,y2=150)
        det1_v1_f1 = DetectionResult(video_configuration_id=1, frame_number=1, class_name="person", confidence=0.92, x1=15,y1=15,x2=65,y2=115)
        
        # Detections for Video 2
        det1_v2_f0 = DetectionResult(video_configuration_id=2, frame_number=0, class_name="car", confidence=0.85, x1=20,y1=20,x2=120,y2=120)
        
        cls.session.add_all([det1_v1_f0, det2_v1_f0, det1_v1_f1, det1_v2_f0])
        cls.session.commit()
        
        # Store some IDs for easy access in tests
        cls.vc1_id = vc1.id
        cls.vc2_id = vc2.id


    @classmethod
    def tearDownClass(cls):
        """Close the session and dispose of the engine after all tests."""
        if cls.session:
            cls.session.close()
        if cls.engine:
            cls.engine.dispose() # Release connection resources

    def setUp(self):
        """Create a new session for each test to ensure test isolation."""
        # While setUpClass creates a session, individual tests might commit/rollback.
        # For query tests, a single session from setUpClass might be fine,
        # but for tests that modify data, a per-test session or careful transaction management is better.
        # Here, we'll reuse the class-level session for query tests for simplicity.
        self.current_session = self.session 


    # --- Tests for get_video_configuration_by_id (Example of an existing function test) ---
    def test_get_video_configuration_by_id_exists(self):
        vc = crud.get_video_configuration_by_id(self.current_session, self.vc1_id)
        self.assertIsNotNone(vc)
        self.assertEqual(vc.id, self.vc1_id)
        self.assertEqual(vc.video_name, "Video 1")

    def test_get_video_configuration_by_id_not_exists(self):
        vc = crud.get_video_configuration_by_id(self.current_session, 999)
        self.assertIsNone(vc)
        
    # --- Tests for add_detection_results (Example, though focus is on queries now) ---
    def test_add_detection_results(self):
        # Add a new video config for this specific test to avoid conflicts
        vc_test_add = VideoConfiguration(id=3, video_path="/test/vid_for_add.mp4", video_name="Vid For Add")
        self.current_session.add(vc_test_add)
        self.current_session.commit()
        vc_test_add_id = vc_test_add.id

        new_detections = [
            {'class_id': 0, 'class_name': 'dog', 'confidence': 0.77, 'bounding_box': (1,2,3,4)},
            {'class_id': 1, 'class_name': 'cat', 'confidence': 0.66, 'bounding_box': (5,6,7,8)}
        ]
        try:
            crud.add_detection_results(self.current_session, vc_test_add_id, 0, new_detections)
        except Exception as e:
            self.fail(f"add_detection_results raised an exception: {e}")

        # Verify
        results_in_db = self.current_session.query(DetectionResult).filter_by(video_configuration_id=vc_test_add_id).all()
        self.assertEqual(len(results_in_db), 2)
        self.assertEqual(results_in_db[0].class_name, "dog")
        self.assertEqual(results_in_db[1].class_name, "cat")
        
        # Clean up by rolling back the session if this were a per-test session
        # or deleting the added data. For simplicity with class-level session, we'll leave it.
        # If using per-test sessions, self.current_session.rollback() would be typical in tearDown.


    # --- Tests for get_detections_for_video ---
    def test_get_detections_for_video_all_frames(self):
        """Test fetching all detections for a specific video."""
        results = crud.get_detections_for_video(self.current_session, self.vc1_id)
        self.assertEqual(len(results), 3) # 2 for frame 0, 1 for frame 1
        self.assertTrue(all(det.video_configuration_id == self.vc1_id for det in results))

    def test_get_detections_for_video_specific_frame(self):
        """Test fetching detections for a specific frame of a video."""
        results = crud.get_detections_for_video(self.current_session, self.vc1_id, frame_number=0)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(det.video_configuration_id == self.vc1_id and det.frame_number == 0 for det in results))
        class_names = {det.class_name for det in results}
        self.assertIn("person", class_names)
        self.assertIn("car", class_names)

    def test_get_detections_for_video_specific_frame_no_detections(self):
        """Test fetching for a frame that has no detections."""
        results = crud.get_detections_for_video(self.current_session, self.vc1_id, frame_number=5) # Frame 5 has no dets
        self.assertEqual(len(results), 0)

    def test_get_detections_for_video_invalid_video_id(self):
        """Test fetching for a non-existent video_config_id."""
        results = crud.get_detections_for_video(self.current_session, 999) # Non-existent ID
        self.assertEqual(len(results), 0)


    # --- Tests for get_detections_by_class ---
    def test_get_detections_by_class_all_videos(self):
        """Test fetching all 'car' detections across all videos."""
        results = crud.get_detections_by_class(self.current_session, "car")
        # Expected: det2_v1_f0 (car from vc1), det1_v2_f0 (car from vc2)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(det.class_name == "car" for det in results))
        video_ids_found = {det.video_configuration_id for det in results}
        self.assertIn(self.vc1_id, video_ids_found)
        self.assertIn(self.vc2_id, video_ids_found)

    def test_get_detections_by_class_specific_video(self):
        """Test fetching 'person' detections for a specific video."""
        results = crud.get_detections_by_class(self.current_session, "person", video_config_id=self.vc1_id)
        # Expected: det1_v1_f0, det1_v1_f1 (both 'person' from vc1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(det.class_name == "person" and det.video_configuration_id == self.vc1_id for det in results))

    def test_get_detections_by_class_no_matches(self):
        """Test fetching for a class name that has no detections."""
        results = crud.get_detections_by_class(self.current_session, "truck")
        self.assertEqual(len(results), 0)

    def test_get_detections_by_class_specific_video_no_matches(self):
        """Test fetching for a class that exists but not in the specified video."""
        results = crud.get_detections_by_class(self.current_session, "person", video_config_id=self.vc2_id) # vc2 has only 'car'
        self.assertEqual(len(results), 0)
        
    def test_get_detections_by_class_empty_class_name(self):
        """Test behavior with empty class name."""
        results = crud.get_detections_by_class(self.current_session, "")
        self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
