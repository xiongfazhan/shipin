import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.processing_core.advanced_detector import AdvancedDetector, DEFAULT_LOCAL_TARGET_CLASSES
from src.processing_core.yolo_detector import YOLODetector # For type hinting and mocking
from src.utils.image_utils import crop_image, map_local_coords_to_global # For asserting calls or direct use if needed

class TestAdvancedDetector(unittest.TestCase):

    def setUp(self):
        """Set up a mock YOLODetector and a dummy frame for each test."""
        self.mock_yolo_detector = MagicMock(spec=YOLODetector)
        self.mock_yolo_detector = MagicMock(spec=YOLODetector)
        # Default initialization for most tests
        self.advanced_detector = AdvancedDetector(
            yolo_detector=self.mock_yolo_detector,
            # Default filter params from AdvancedDetector:
            # min_confidence_filter=0.5, allowed_classes_filter=None, 
            # merge_iou_threshold=0.5, class_specific_nms=True
        )
        self.dummy_frame = np.random.randint(0, 256, size=(480, 640, 3), dtype=np.uint8)

    def test_initialization(self):
        """Test AdvancedDetector initialization including filter parameters."""
        self.assertIsNotNone(self.advanced_detector.yolo_detector)
        self.assertEqual(self.advanced_detector.local_target_classes, DEFAULT_LOCAL_TARGET_CLASSES)
        self.assertEqual(self.advanced_detector.local_target_confidence_threshold, 0.4)
        # Test default filter params
        self.assertEqual(self.advanced_detector.min_confidence_filter, 0.5)
        self.assertIsNone(self.advanced_detector.allowed_classes_filter)
        self.assertEqual(self.advanced_detector.merge_iou_threshold, 0.5)
        self.assertTrue(self.advanced_detector.class_specific_nms)


        custom_targets = ['cat', 'dog']
        custom_thresh = 0.7
        custom_min_conf_filter = 0.6
        custom_allowed_classes = ['person']
        custom_merge_iou = 0.6
        custom_class_nms = False

        adv_detector_custom = AdvancedDetector(
            self.mock_yolo_detector, 
            local_target_classes=custom_targets,
            local_target_confidence_threshold=custom_thresh,
            min_confidence_filter=custom_min_conf_filter,
            allowed_classes_filter=custom_allowed_classes,
            merge_iou_threshold=custom_merge_iou,
            class_specific_nms=custom_class_nms
        )
        self.assertEqual(adv_detector_custom.local_target_classes, custom_targets)
        self.assertEqual(adv_detector_custom.local_target_confidence_threshold, custom_thresh)
        self.assertEqual(adv_detector_custom.min_confidence_filter, custom_min_conf_filter)
        self.assertEqual(adv_detector_custom.allowed_classes_filter, custom_allowed_classes)
        self.assertEqual(adv_detector_custom.merge_iou_threshold, custom_merge_iou)
        self.assertEqual(adv_detector_custom.class_specific_nms, custom_class_nms)


    @patch('src.processing_core.advanced_detector.result_processor.merge_detections')
    @patch('src.processing_core.advanced_detector.result_processor.filter_detections')
    def test_detect_with_localization_no_initial_detections(self, mock_filter_detections, mock_merge_detections):
        """Test behavior when initial detection yields nothing."""
        self.mock_yolo_detector.detect_objects.return_value = [[]] # One frame, no detections
        
        # Mock merge and filter to return empty if called with empty
        mock_merge_detections.return_value = []
        mock_filter_detections.return_value = []
        
        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)
        
        self.mock_yolo_detector.detect_objects.assert_called_once_with([self.dummy_frame])
        # Merge should be called with empty list of raw detections
        mock_merge_detections.assert_called_once_with([], iou_threshold=self.advanced_detector.merge_iou_threshold, class_specific_nms=self.advanced_detector.class_specific_nms)
        # Filter should be called with the result of merge (empty list)
        expected_filter_config = {
            'min_confidence': self.advanced_detector.min_confidence_filter,
            'allowed_classes': self.advanced_detector.allowed_classes_filter,
            'max_detections_per_frame': None
        }
        mock_filter_detections.assert_called_once_with([], expected_filter_config)
        self.assertEqual(final_detections, [])


    @patch('src.processing_core.advanced_detector.result_processor.merge_detections')
    @patch('src.processing_core.advanced_detector.result_processor.filter_detections')
    def test_detect_with_localization_no_local_targets_found(self, mock_filter_detections, mock_merge_detections):
        """Test behavior when initial detections do not meet local target criteria, ensuring merge/filter are still called."""
        raw_initial_detections = [
            {'class_name': 'car', 'confidence': 0.8, 'bounding_box': (10, 10, 50, 50), 'class_id': 3},
            {'class_name': 'tree', 'confidence': 0.9, 'bounding_box': (60, 60, 100, 100), 'class_id': 10}
        ]
        self.mock_yolo_detector.detect_objects.return_value = [raw_initial_detections]
        
        # Mock merge and filter to pass through the raw detections
        mock_merge_detections.return_value = raw_initial_detections # Simulating no merges needed
        mock_filter_detections.return_value = raw_initial_detections # Simulating no filtering needed for this test focus
        
        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)
        
        self.mock_yolo_detector.detect_objects.assert_called_once_with([self.dummy_frame])
        # Merge should be called with the raw initial detections
        mock_merge_detections.assert_called_once_with(raw_initial_detections, iou_threshold=self.advanced_detector.merge_iou_threshold, class_specific_nms=self.advanced_detector.class_specific_nms)
        # Filter should be called with the result of merge
        expected_filter_config = {
            'min_confidence': self.advanced_detector.min_confidence_filter,
            'allowed_classes': self.advanced_detector.allowed_classes_filter,
            'max_detections_per_frame': None
        }
        mock_filter_detections.assert_called_once_with(raw_initial_detections, expected_filter_config) # raw_initial_detections is output of merge here
        
        self.assertEqual(final_detections, raw_initial_detections, "Should return initial detections if no local targets and filters pass them.")


    @patch('src.processing_core.advanced_detector.result_processor.merge_detections')
    @patch('src.processing_core.advanced_detector.result_processor.filter_detections')
    def test_detect_with_localization_local_target_below_threshold(self, mock_filter_detections, mock_merge_detections):
        """Test when a potential local target's confidence is below threshold."""
        raw_initial_detections = [
            {'class_name': 'desk', 'confidence': 0.3, 'bounding_box': (10, 10, 210, 210), 'class_id': 5} # 'desk' is a local target
        ]
        self.mock_yolo_detector.detect_objects.return_value = [raw_initial_detections]
        
        mock_merge_detections.return_value = raw_initial_detections
        mock_filter_detections.return_value = raw_initial_detections # Assume it passes filter for now
        
        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)
        
        self.mock_yolo_detector.detect_objects.assert_called_once_with([self.dummy_frame])
        mock_merge_detections.assert_called_once_with(raw_initial_detections, iou_threshold=self.advanced_detector.merge_iou_threshold, class_specific_nms=self.advanced_detector.class_specific_nms)
        expected_filter_config = {
            'min_confidence': self.advanced_detector.min_confidence_filter,
            'allowed_classes': self.advanced_detector.allowed_classes_filter,
            'max_detections_per_frame': None
        }
        mock_filter_detections.assert_called_once_with(raw_initial_detections, expected_filter_config)
        
        self.assertEqual(final_detections, raw_initial_detections) 
        # Ensure YOLODetector was only called once (no secondary scan)
        self.assertEqual(self.mock_yolo_detector.detect_objects.call_count, 1)


    @patch('src.processing_core.advanced_detector.crop_image') 
    @patch('src.processing_core.advanced_detector.result_processor.merge_detections')
    @patch('src.processing_core.advanced_detector.result_processor.filter_detections')
    def test_detect_with_localization_one_local_target_found_and_processed(self, mock_filter_detections, mock_merge_detections, mock_crop_image):
        """Test full flow with one local target and secondary detections."""
        target_desk_box = (50, 50, 350, 250) # x1,y1,x2,y2 -> width=300, height=200
        initial_detections_list = [
            {'class_name': 'desk', 'confidence': 0.9, 'bounding_box': target_desk_box, 'class_id': 0},
            {'class_name': 'plant', 'confidence': 0.7, 'bounding_box': (0,0,30,30), 'class_id': 1}
        ]

        # Mocking crop_image
        # It should return a valid image for the secondary detection to proceed
        mock_cropped_desk_area = np.random.randint(0, 256, size=(200, 300, 3), dtype=np.uint8) # h, w, c
        mock_crop_image.return_value = mock_cropped_desk_area

        # Mocking YOLODetector's response
        # First call (initial scan)
        mock_initial_response = [initial_detections_list]
        # Second call (secondary scan on cropped desk)
        secondary_detections_on_crop_list = [
            {'class_name': 'laptop', 'confidence': 0.85, 'bounding_box': (10, 20, 110, 120), 'class_id': 2}, # Local coords
            {'class_name': 'mouse', 'confidence': 0.75, 'bounding_box': (120, 130, 140, 150), 'class_id': 3} # Local coords
        ]
        mock_secondary_response = [secondary_detections_on_crop_list]
        
        self.mock_yolo_detector.detect_objects.side_effect = [mock_initial_response, mock_secondary_response]

        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)

        # Assertions
        self.assertEqual(self.mock_yolo_detector.detect_objects.call_count, 2)
        # Call 1: Initial scan
        self.mock_yolo_detector.detect_objects.assert_any_call([self.dummy_frame])
        # Call 2: Secondary scan on cropped image
        # Need to check the argument to the second call was the mock_cropped_desk_area
        # (or an equivalent, due to how MagicMock handles array comparisons)
        # For simplicity, we check that a call was made with a list containing one np.ndarray
        secondary_call_args = self.mock_yolo_detector.detect_objects.call_args_list[1][0][0]
        self.assertIsInstance(secondary_call_args, list)
        self.assertIsInstance(secondary_call_args[0], np.ndarray)
        self.assertEqual(secondary_call_args[0].shape, mock_cropped_desk_area.shape)


        mock_crop_image.assert_called_once_with(self.dummy_frame, target_desk_box)
        
        self.assertEqual(len(final_detections), 
                         len(initial_detections_list) + len(secondary_detections_on_crop_list))

        # Check initial detections are present
        self.assertIn(initial_detections_list[0], final_detections)
        self.assertIn(initial_detections_list[1], final_detections)

        # Check remapped secondary detections
        # Laptop: local (10,20,110,120), crop_origin (50,50)
        # Global: (10+50, 20+50, 110+50, 120+50) = (60, 70, 160, 170)
        expected_global_laptop_box = (60, 70, 160, 170)
        # Mouse: local (120,130,140,150), crop_origin (50,50)
        # Global: (120+50, 130+50, 140+50, 150+50) = (170, 180, 190, 200)
        expected_global_mouse_box = (170, 180, 190, 200)

        found_laptop = False
        found_mouse = False
        for det in final_detections:
            if det['class_name'] == 'laptop':
                self.assertEqual(det['bounding_box'], expected_global_laptop_box)
                self.assertEqual(det.get('source'), 'secondary_scan')
                found_laptop = True
            elif det['class_name'] == 'mouse':
                self.assertEqual(det['bounding_box'], expected_global_mouse_box)
                self.assertEqual(det.get('source'), 'secondary_scan')
                found_mouse = True
        
        self.assertTrue(found_laptop, "Remapped laptop detection not found.")
        self.assertTrue(found_mouse, "Remapped mouse detection not found.")

    @patch('src.processing_core.advanced_detector.crop_image')
    def test_detect_with_localization_crop_fails(self, mock_crop_image):
        """Test behavior when cropping fails (returns None)."""
        target_desk_box = (50, 50, 350, 250)
        initial_detections_list = [
            {'class_name': 'desk', 'confidence': 0.9, 'bounding_box': target_desk_box, 'class_id':0}
        ]
        self.mock_yolo_detector.detect_objects.return_value = [initial_detections_list] # Only initial call
        
        mock_crop_image.return_value = None # Simulate crop failure

        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)

        self.mock_yolo_detector.detect_objects.assert_called_once_with([self.dummy_frame])
        mock_crop_image.assert_called_once_with(self.dummy_frame, target_desk_box)
        
        # Should only contain initial detections as secondary scan was skipped
        self.assertEqual(final_detections, initial_detections_list)

    @patch('src.processing_core.advanced_detector.crop_image')
    def test_detect_with_localization_secondary_scan_no_detections(self, mock_crop_image):
        """Test when secondary scan on a valid crop yields no new detections."""
        target_desk_box = (50, 50, 350, 250)
        initial_detections_list = [
            {'class_name': 'desk', 'confidence': 0.9, 'bounding_box': target_desk_box, 'class_id':0}
        ]
        
        mock_cropped_desk_area = np.random.randint(0, 256, size=(200, 300, 3), dtype=np.uint8)
        mock_crop_image.return_value = mock_cropped_desk_area
        
        # YOLO detector calls: initial, then secondary (which finds nothing)
        self.mock_yolo_detector.detect_objects.side_effect = [
            [initial_detections_list], # Initial results
            [[]]                       # Secondary results (no detections on crop)
        ]

        final_detections = self.advanced_detector.detect_with_localization(self.dummy_frame)

        self.assertEqual(self.mock_yolo_detector.detect_objects.call_count, 2)
        mock_crop_image.assert_called_once_with(self.dummy_frame, target_desk_box)
        
        # Final detections should be same as initial ones
        self.assertEqual(final_detections, initial_detections_list)

    @patch('src.processing_core.advanced_detector.result_processor.merge_detections')
    @patch('src.processing_core.advanced_detector.result_processor.filter_detections')
    def test_detect_with_localization_filter_config_override(self, mock_filter_detections, mock_merge_detections):
        """Test overriding filter_config at call time."""
        raw_detections = [{'class_name': 'car', 'confidence': 0.8, 'bounding_box': (10,10,50,50), 'class_id':3}]
        self.mock_yolo_detector.detect_objects.return_value = [raw_detections] # Initial scan
        
        # Mock merge_detections to return the raw_detections (as if no merge happened)
        mock_merge_detections.return_value = raw_detections
        
        # Mock filter_detections to also return raw_detections for simplicity, 
        # we're focusing on whether it's called with the right config.
        mock_filter_detections.return_value = raw_detections 

        override_config = {'min_confidence': 0.75, 'allowed_classes': ['car']}
        
        # Expected config that filter_detections should be called with:
        # It's the override_config + any default keys not in override (like max_detections_per_frame)
        expected_call_config = {
            'min_confidence': 0.75, # from override
            'allowed_classes': ['car'], # from override
            'max_detections_per_frame': None # from AdvancedDetector's default handling if not in override
        }
        
        # Call the method with the override
        self.advanced_detector.detect_with_localization(self.dummy_frame, filter_config_override=override_config)
        
        # Assert that yolo_detector was called for the initial scan
        self.mock_yolo_detector.detect_objects.assert_called_once_with([self.dummy_frame])
        
        # Assert that merge_detections was called with the raw detections from yolo
        mock_merge_detections.assert_called_once_with(
            raw_detections, 
            iou_threshold=self.advanced_detector.merge_iou_threshold, 
            class_specific_nms=self.advanced_detector.class_specific_nms
        )
        
        # Assert that filter_detections was called with the (mocked) result of merge_detections
        # AND with the correctly composed configuration (override + defaults)
        mock_filter_detections.assert_called_once_with(raw_detections, expected_call_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
