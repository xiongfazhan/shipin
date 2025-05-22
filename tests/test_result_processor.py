import unittest
import sys
import os

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.processing_core.result_processor import merge_detections, filter_detections
from src.utils.image_utils import calculate_iou # For verification or direct use in tests if needed

class TestResultProcessor(unittest.TestCase):

    def setUp(self):
        # Sample detections for use in multiple tests
        self.det_person1_high = {'class_id': 0, 'class_name': 'person', 'bounding_box': (50, 50, 150, 250), 'confidence': 0.95}
        self.det_person2_overlap_high = {'class_id': 0, 'class_name': 'person', 'bounding_box': (60, 60, 160, 260), 'confidence': 0.85} # Overlaps person1
        self.det_person3_distinct_mid = {'class_id': 0, 'class_name': 'person', 'bounding_box': (300, 50, 350, 150), 'confidence': 0.75}
        self.det_person4_low = {'class_id': 0, 'class_name': 'person', 'bounding_box': (400, 50, 450, 150), 'confidence': 0.30}
        
        self.det_car1_high = {'class_id': 2, 'class_name': 'car', 'bounding_box': (200, 100, 300, 200), 'confidence': 0.90}
        self.det_car2_overlap_high = {'class_id': 2, 'class_name': 'car', 'bounding_box': (210, 105, 310, 205), 'confidence': 0.50} # Overlaps car1
        
        self.det_bicycle_mid = {'class_id': 1, 'class_name': 'bicycle', 'bounding_box': (280, 110, 380, 220), 'confidence': 0.70} # May overlap car1, different class
        self.det_cat_high = {'class_id': 15, 'class_name': 'cat', 'bounding_box': (500, 200, 580, 280), 'confidence': 0.92}

        self.sample_detections = [
            self.det_person1_high, self.det_person2_overlap_high, self.det_person3_distinct_mid, self.det_person4_low,
            self.det_car1_high, self.det_car2_overlap_high, self.det_bicycle_mid, self.det_cat_high
        ]
        # Total 8 detections initially


    # --- Tests for merge_detections ---
    def test_merge_detections_empty_input(self):
        self.assertEqual(merge_detections([]), [])

    def test_merge_detections_no_overlap(self):
        """Test with detections that do not overlap significantly."""
        no_overlap_detections = [self.det_person1_high, self.det_car1_high, self.det_cat_high]
        # Sorted by confidence: person1 (0.95), cat (0.92), car1 (0.90)
        result = merge_detections(no_overlap_detections, iou_threshold=0.5, class_specific_nms=True)
        self.assertEqual(len(result), 3)
        self.assertCountEqual(result, no_overlap_detections, "Should keep all non-overlapping detections.")
        # Check order (by confidence)
        self.assertEqual(result[0], self.det_person1_high)
        self.assertEqual(result[1], self.det_cat_high)
        self.assertEqual(result[2], self.det_car1_high)


    def test_merge_detections_class_specific_nms_suppression(self):
        """Test class-specific NMS where overlapping detections of same class are suppressed."""
        # person1 (0.95) and person2_overlap (0.85) should result in person1 being kept.
        # car1 (0.90) and car2_overlap (0.50) should result in car1 being kept.
        # bicycle (0.70) might overlap car1, but is different class, so should be kept.
        # cat (0.92) is distinct.
        # person3_distinct (0.75) is distinct.
        # person4_low (0.30) is distinct.
        
        # IoU between person1 and person2:
        # p1=(50,50,150,250) area=20000; p2=(60,60,160,260) area=20000
        # intersect: xL=60,yT=60,xR=150,yB=250 -> (150-60)*(250-60) = 90*190 = 17100
        # union = 20000+20000-17100 = 22900. IoU = 17100/22900 approx 0.74. High overlap.
        
        # IoU between car1 and car2:
        # c1=(200,100,300,200) area=10000; c2=(210,105,310,205) area=10000
        # intersect: xL=210,yT=105,xR=300,yB=200 -> (300-210)*(200-105) = 90*95 = 8550
        # union = 10000+10000-8550 = 11450. IoU = 8550/11450 approx 0.74. High overlap.

        result = merge_detections(self.sample_detections, iou_threshold=0.5, class_specific_nms=True)
        
        expected_kept = [
            self.det_person1_high, # person2 suppressed
            self.det_car1_high,    # car2 suppressed
            self.det_bicycle_mid,
            self.det_cat_high,
            self.det_person3_distinct_mid,
            self.det_person4_low
        ]
        self.assertEqual(len(result), len(expected_kept))
        # Use assertCountEqual because NMS processing order within class might not be stable for confidence if classes are processed one by one
        # However, the overall list from merge_detections is not guaranteed to be sorted by confidence if class_specific_nms=True.
        # Let's check if all expected are present.
        for expected_det in expected_kept:
            self.assertIn(expected_det, result, f"Expected detection {expected_det} to be in merged results.")
        
        # Check that suppressed ones are NOT present
        self.assertNotIn(self.det_person2_overlap_high, result)
        self.assertNotIn(self.det_car2_overlap_high, result)


    def test_merge_detections_global_nms_suppression(self):
        """Test global NMS. If bicycle overlaps car1 significantly, one might suppress the other."""
        # As calculated in result_processor.py example, IoU car1-bicycle is low (~0.09).
        # So, global NMS should behave similarly to class-specific NMS in this particular case.
        # If we had a high-confidence bicycle highly overlapping a low-confidence car,
        # the bicycle would suppress the car.
        
        result = merge_detections(self.sample_detections, iou_threshold=0.5, class_specific_nms=False)
        
        # Expected output should be sorted by confidence because global NMS processes the full sorted list.
        expected_kept_sorted_confidence = sorted([
            self.det_person1_high,
            self.det_car1_high,
            self.det_bicycle_mid,
            self.det_cat_high,
            self.det_person3_distinct_mid,
            self.det_person4_low
        ], key=lambda x: x['confidence'], reverse=True)
        
        self.assertEqual(len(result), len(expected_kept_sorted_confidence))
        self.assertEqual(result, expected_kept_sorted_confidence, "Global NMS result not sorted by confidence or content mismatch.")
        
        self.assertNotIn(self.det_person2_overlap_high, result)
        self.assertNotIn(self.det_car2_overlap_high, result)

    def test_merge_detections_iou_threshold_effect(self):
        """Test how different IoU thresholds affect suppression."""
        # Using person1 (0.95) and person2_overlap (0.85). IoU is ~0.74.
        detections_to_test = [self.det_person1_high, self.det_person2_overlap_high]
        
        # With IoU threshold 0.8 (higher than actual IoU), person2 should NOT be suppressed
        result_high_thresh = merge_detections(detections_to_test, iou_threshold=0.8, class_specific_nms=True)
        self.assertEqual(len(result_high_thresh), 2)
        self.assertCountEqual(result_high_thresh, detections_to_test)

        # With IoU threshold 0.7 (lower than actual IoU), person2 SHOULD be suppressed
        result_low_thresh = merge_detections(detections_to_test, iou_threshold=0.7, class_specific_nms=True)
        self.assertEqual(len(result_low_thresh), 1)
        self.assertIn(self.det_person1_high, result_low_thresh)


    # --- Tests for filter_detections ---
    def test_filter_detections_empty_input(self):
        self.assertEqual(filter_detections([], {}), [])

    def test_filter_by_min_confidence(self):
        config = {'min_confidence': 0.80} # Expect person4_low (0.3), bicycle (0.7), car2 (0.5), person3 (0.75) to be filtered
        # Input: 8 detections
        # Keep: person1 (0.95), person2 (0.85), car1 (0.90), cat (0.92)
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), 4)
        for det in result:
            self.assertGreaterEqual(det['confidence'], 0.80)

    def test_filter_by_allowed_classes(self):
        config = {'allowed_classes': ['person', 'cat']}
        # Keep: all persons (4), cat (1) = 5 detections
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), 5)
        for det in result:
            self.assertIn(det['class_name'], ['person', 'cat'])

    def test_filter_by_allowed_classes_empty_list(self):
        """Empty allowed_classes list should mean keep all classes."""
        config = {'allowed_classes': []}
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), len(self.sample_detections)) # Keep all

    def test_filter_by_allowed_classes_none(self):
        """None for allowed_classes should mean keep all classes."""
        config = {'allowed_classes': None}
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), len(self.sample_detections)) # Keep all

    def test_filter_by_max_detections_per_frame(self):
        # Detections should be sorted by confidence before applying max limit
        config = {'max_detections_per_frame': 3}
        # sample_detections sorted by conf:
        # p1(0.95), cat(0.92), car1(0.90), p2(0.85), p3(0.75), bic(0.70), car2(0.50), p4(0.30)
        # Top 3: p1, cat, car1
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), 3)
        
        expected_top_3_conf = sorted(self.sample_detections, key=lambda x: x['confidence'], reverse=True)[:3]
        # Order might differ if confidences are equal, so use assertCountEqual for content.
        # The filter_detections function sorts internally if max_detections is applied.
        self.assertEqual(result, expected_top_3_conf)


    def test_filter_combined_filters(self):
        config = {
            'min_confidence': 0.70,
            'allowed_classes': ['person', 'car'],
            'max_detections_per_frame': 2
        }
        # Step 1: min_confidence 0.70
        # Keep: p1(0.95), p2(0.85), p3(0.75), car1(0.90), bic(0.70), cat(0.92) -- (car2, p4 filtered out)
        # Result: 6 detections
        
        # Step 2: allowed_classes ['person', 'car']
        # Keep: p1(0.95), p2(0.85), p3(0.75), car1(0.90) -- (bic, cat filtered out)
        # Result: 4 detections
        
        # Step 3: max_detections_per_frame 2 (sorted by confidence)
        # Sorted: p1(0.95), car1(0.90), p2(0.85), p3(0.75)
        # Top 2: p1(0.95), car1(0.90)
        
        result = filter_detections(self.sample_detections, config)
        self.assertEqual(len(result), 2)
        self.assertIn(self.det_person1_high, result)
        self.assertIn(self.det_car1_high, result)

    def test_filter_invalid_config_values(self):
        # Test with invalid min_confidence
        config_invalid_conf = {'min_confidence': 'high'}
        result = filter_detections(self.sample_detections, config_invalid_conf)
        self.assertEqual(len(result), len(self.sample_detections), "Invalid confidence value should skip conf filter.")

        # Test with invalid allowed_classes
        config_invalid_classes = {'allowed_classes': 'person'} # Should be a list
        result = filter_detections(self.sample_detections, config_invalid_classes)
        self.assertEqual(len(result), len(self.sample_detections), "Invalid allowed_classes value should skip class filter.")

        # Test with invalid max_detections
        config_invalid_max = {'max_detections_per_frame': -1}
        result = filter_detections(self.sample_detections, config_invalid_max)
        self.assertEqual(len(result), len(self.sample_detections), "Invalid max_detections value should skip max_detections filter.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
