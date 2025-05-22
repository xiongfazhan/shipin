import unittest
import numpy as np
import os
import sys

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.processing_core.yolo_detector import YOLODetector

# Define path for a sample image that might be created by yolo_detector.py's main block
# or can be manually placed for more robust testing.
SAMPLE_IMAGE_DIR = os.path.join(parent_dir, "data")
SAMPLE_IMAGE_FILENAME = "sample_image_for_detector_test.jpg" # Use a distinct name
SAMPLE_IMAGE_PATH = os.path.join(SAMPLE_IMAGE_DIR, SAMPLE_IMAGE_FILENAME)

def create_sample_image_for_tests(image_path):
    """Helper function to create a dummy image with some shapes for testing."""
    if not os.path.exists(os.path.dirname(image_path)):
        os.makedirs(os.path.dirname(image_path))
    
    try:
        import cv2 # Local import for this utility
        img = np.zeros((480, 640, 3), dtype=np.uint8) # Black background
        # Add some elements that yolov8n *might* pick up, or just to have content
        cv2.rectangle(img, (50, 50), (150, 150), (0, 0, 255), -1)  # Red square
        cv2.rectangle(img, (200, 100), (350, 300), (0, 255, 0), -1) # Green rectangle
        cv2.circle(img, (500, 250), 50, (255, 0, 0), -1) # Blue circle
        # Add some text, unlikely to be detected as an object, but makes image non-trivial
        cv2.putText(img, "Test Image", (200, 400), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        cv2.imwrite(image_path, img)
        print(f"INFO (test setup): Dummy sample image created at {image_path}")
        return True
    except ImportError:
        print("WARNING (test setup): OpenCV (cv2) not available. Cannot create sample image for detector tests.")
        return False
    except Exception as e:
        print(f"ERROR (test setup): Could not create sample image at {image_path}: {e}")
        return False

class TestYOLODetector(unittest.TestCase):

    detector_instance = None

    @classmethod
    def setUpClass(cls):
        """Initialize the YOLODetector once for all tests."""
        print("INFO (TestYOLODetector): Setting up class. Initializing YOLODetector with 'yolov8n.pt'.")
        try:
            # This might download the model if not present, requires internet.
            cls.detector_instance = YOLODetector(model_name='yolov8n.pt')
        except Exception as e:
            # If detector fails to initialize (e.g. no internet for model download),
            # tests that require it will fail or be skipped.
            print(f"CRITICAL (TestYOLODetector): Failed to initialize YOLODetector: {e}. Some tests may fail.")
            # Not raising error here to allow tests that don't need a live model to potentially run
            # or to see how it behaves when model loading fails.
            # However, most tests below *do* rely on it.

        # Create a sample image for testing object detection if it doesn't exist
        if not os.path.exists(SAMPLE_IMAGE_PATH):
            create_sample_image_for_tests(SAMPLE_IMAGE_PATH)
        else:
            print(f"INFO (TestYOLODetector): Sample image {SAMPLE_IMAGE_PATH} already exists.")

    @classmethod
    def tearDownClass(cls):
        """Clean up resources, e.g., delete the sample image."""
        print("INFO (TestYOLODetector): Tearing down class.")
        if os.path.exists(SAMPLE_IMAGE_PATH):
            try:
                # os.remove(SAMPLE_IMAGE_PATH) # Optional: remove if it's purely for testing
                # print(f"INFO (TestYOLODetector): Sample image {SAMPLE_IMAGE_PATH} removed.")
                pass # Decided to keep the image for now for easier manual inspection post-test
            except OSError as e:
                print(f"WARNING (TestYOLODetector): Could not remove sample image {SAMPLE_IMAGE_PATH}: {e}")
        
        # No specific cleanup for detector_instance needed unless it held open files/connections not managed by YOLO lib

    def test_01_detector_initialization(self):
        """Test if the YOLODetector initializes and loads the model."""
        if self.detector_instance is None:
            self.fail("YOLODetector instance was not created in setUpClass.")
        self.assertIsNotNone(self.detector_instance, "YOLODetector instance should not be None.")
        self.assertIsNotNone(self.detector_instance.model, "YOLO model should be loaded.")
        # Check if the model is a YOLO model (basic check)
        from ultralytics import YOLO as UL_YOLO
        self.assertIsInstance(self.detector_instance.model, UL_YOLO, "Model is not an Ultralytics YOLO instance.")


    def test_02_detect_objects_empty_input(self):
        """Test detect_objects with an empty list of frames."""
        if not self.detector_instance or not self.detector_instance.model:
            self.skipTest("YOLODetector not initialized or model not loaded.")
        
        detections = self.detector_instance.detect_objects([])
        self.assertEqual(detections, [], "Expected an empty list for empty input frames.")

    def test_03_detect_objects_dummy_frames(self):
        """Test detect_objects with dummy (e.g., black) frames."""
        if not self.detector_instance or not self.detector_instance.model:
            self.skipTest("YOLODetector not initialized or model not loaded.")

        # Create a black frame and a white frame
        dummy_black_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        dummy_white_frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        frames = [dummy_black_frame, dummy_white_frame]
        
        detections = self.detector_instance.detect_objects(frames)
        
        self.assertIsInstance(detections, list, "Detections should be a list.")
        self.assertEqual(len(detections), len(frames), "Should return results for each frame.")
        
        for frame_dets in detections:
            self.assertIsInstance(frame_dets, list, "Each frame's detections should be a list.")
            for det in frame_dets: # If any detections are found (unlikely for blank frames, but check structure)
                self.assertIsInstance(det, dict, "Each detection should be a dictionary.")
                self.assertIn('class_id', det)
                self.assertIn('class_name', det)
                self.assertIn('bounding_box', det)
                self.assertIn('confidence', det)
                self.assertIsInstance(det['bounding_box'], tuple, "Bounding box should be a tuple.")
                self.assertEqual(len(det['bounding_box']), 4, "Bounding box should have 4 coordinates.")

    def test_04_detect_objects_with_sample_image(self):
        """Test detect_objects with a sample image file that might contain objects."""
        if not self.detector_instance or not self.detector_instance.model:
            self.skipTest("YOLODetector not initialized or model not loaded.")
        
        if not os.path.exists(SAMPLE_IMAGE_PATH):
            self.skipTest(f"Sample image {SAMPLE_IMAGE_PATH} not found. Cannot run this test.")

        try:
            import cv2 # Local import
            img = cv2.imread(SAMPLE_IMAGE_PATH)
            if img is None:
                self.fail(f"Failed to read sample image {SAMPLE_IMAGE_PATH} using OpenCV.")
        except ImportError:
            self.skipTest("OpenCV (cv2) not available. Cannot load sample image for this test.")
            return
        except Exception as e:
            self.fail(f"Error loading sample image {SAMPLE_IMAGE_PATH}: {e}")
            return

        frames = [img]
        detections = self.detector_instance.detect_objects(frames)
        
        self.assertIsInstance(detections, list)
        self.assertEqual(len(detections), 1) # One frame processed
        
        # For the first (and only) frame's detections:
        frame_dets = detections[0]
        self.assertIsInstance(frame_dets, list)
        
        # We can't assert that objects *will* be detected in the dummy sample image,
        # as yolov8n is complex and the dummy image is simple.
        # But if they are, they should follow the structure.
        print(f"INFO (TestYOLODetector): Found {len(frame_dets)} detections in the sample image '{SAMPLE_IMAGE_PATH}'.")
        if frame_dets: # If any objects were detected
            print("Sample image detections:")
            for det_idx, det in enumerate(frame_dets):
                print(f"  Det {det_idx}: Class '{det['class_name']}', Conf: {det['confidence']:.2f}, Box: {det['bounding_box']}")
                self.assertIsInstance(det, dict)
                self.assertIn('class_id', det)
                self.assertIsInstance(det['class_id'], int)
                self.assertIn('class_name', det)
                self.assertIsInstance(det['class_name'], str)
                self.assertIn('bounding_box', det)
                self.assertIsInstance(det['bounding_box'], tuple)
                self.assertEqual(len(det['bounding_box']), 4)
                self.assertIn('confidence', det)
                self.assertIsInstance(det['confidence'], float)
        else:
            print(f"INFO (TestYOLODetector): No objects detected in sample image '{SAMPLE_IMAGE_PATH}'. This is acceptable for a simple dummy image.")


    def test_05_model_failure_graceful_handling(self):
        """Test how detect_objects behaves if model wasn't loaded."""
        # Temporarily create a detector instance where model loading might fail
        # For this test, we assume model loading is the point of failure.
        # One way to simulate this is to use an invalid model name,
        # but YOLODetector's __init__ might raise an error then.
        # Let's test the case where self.model is None.
        
        # This test requires modifying the instance or creating a special one.
        # We'll create a new instance and manually set its model to None.
        temp_detector = YOLODetector(model_name='yolov8n.pt') # Assume this works
        temp_detector.model = None # Manually simulate a failure post-init or a bad init path
        
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        detections = temp_detector.detect_objects([dummy_frame])
        
        self.assertIsInstance(detections, list, "Detections should be a list even if model is None.")
        self.assertEqual(len(detections), 1, "Should return a list per frame even if model is None.")
        self.assertEqual(detections[0], [], "Detections for the frame should be empty if model is None.")


if __name__ == '__main__':
    print("Running tests for YOLODetector...")
    # To ensure setUpClass runs, and for consistent test execution:
    suite = unittest.TestSuite()
    # Add tests in a specific order if dependencies exist (e.g., init before others)
    suite.addTest(unittest.makeSuite(TestYOLODetector))
    # If using older unittest that doesn't sort by name for makeSuite, or to be explicit:
    # test_names = sorted([name for name in dir(TestYOLODetector) if name.startswith('test_')])
    # for name in test_names:
    #    suite.addTest(TestYOLODetector(name))
    
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
