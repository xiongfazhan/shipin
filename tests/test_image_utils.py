import unittest
import numpy as np
import sys
import os

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.utils.image_utils import crop_image, map_local_coords_to_global

class TestImageUtils(unittest.TestCase):

    def setUp(self):
        """Set up a dummy image for each test."""
        self.original_image = np.random.randint(0, 256, size=(100, 150, 3), dtype=np.uint8)
        self.img_height, self.img_width = self.original_image.shape[:2]

    def test_crop_image_valid_box(self):
        """Test cropping with a valid bounding box."""
        crop_box = (10, 20, 60, 80) # x1, y1, x2, y2
        cropped = crop_image(self.original_image, crop_box)
        self.assertIsNotNone(cropped, "Cropped image should not be None for a valid box.")
        # Expected: height = y2-y1 = 60, width = x2-x1 = 50
        self.assertEqual(cropped.shape, (60, 50, 3), "Cropped image has incorrect dimensions.")

    def test_crop_image_box_at_edges(self):
        """Test cropping with a box that is exactly the image dimensions."""
        crop_box = (0, 0, self.img_width, self.img_height)
        cropped = crop_image(self.original_image, crop_box)
        self.assertIsNotNone(cropped)
        self.assertEqual(cropped.shape, self.original_image.shape, "Cropping full image should yield same dimensions.")
        self.assertTrue(np.array_equal(cropped, self.original_image), "Cropping full image should yield identical image.")

    def test_crop_image_invalid_box_dimensions(self):
        """Test cropping with invalid box dimensions (e.g., x1 >= x2)."""
        crop_box_invalid_x = (70, 20, 30, 80) # x1 > x2
        cropped_x = crop_image(self.original_image, crop_box_invalid_x)
        self.assertIsNone(cropped_x, "Should return None for x1 > x2.")

        crop_box_invalid_y = (10, 80, 60, 20) # y1 > y2
        cropped_y = crop_image(self.original_image, crop_box_invalid_y)
        self.assertIsNone(cropped_y, "Should return None for y1 > y2.")
        
        crop_box_zero_width = (10, 20, 10, 80) # x1 == x2
        cropped_zw = crop_image(self.original_image, crop_box_zero_width)
        self.assertIsNone(cropped_zw, "Should return None for zero-width box.")

        crop_box_zero_height = (10, 20, 60, 20) # y1 == y2
        cropped_zh = crop_image(self.original_image, crop_box_zero_height)
        self.assertIsNone(cropped_zh, "Should return None for zero-height box.")

    def test_crop_image_box_partially_outside_clamping(self):
        """Test cropping with a box partially outside; should clamp."""
        # Box: x1<0, y1<0, x2>width, y2>height
        crop_box = (-10, -20, self.img_width + 10, self.img_height + 20)
        cropped = crop_image(self.original_image, crop_box)
        self.assertIsNotNone(cropped, "Cropped image should not be None when clamping is possible.")
        # Expected: should be clamped to (0, 0, self.img_width, self.img_height)
        self.assertEqual(cropped.shape, self.original_image.shape, "Clamped box should result in original image dimensions.")

    def test_crop_image_box_fully_outside(self):
        """Test cropping with a box fully outside image bounds."""
        crop_box_right = (self.img_width + 10, 10, self.img_width + 50, 50)
        self.assertIsNone(crop_image(self.original_image, crop_box_right), "Box fully to the right should return None.")

        crop_box_left = (-50, 10, -10, 50)
        self.assertIsNone(crop_image(self.original_image, crop_box_left), "Box fully to the left should return None.")
        
        crop_box_below = (10, self.img_height + 10, 50, self.img_height + 50)
        self.assertIsNone(crop_image(self.original_image, crop_box_below), "Box fully below should return None.")

        crop_box_above = (10, -50, 50, -10)
        self.assertIsNone(crop_image(self.original_image, crop_box_above), "Box fully above should return None.")

    def test_crop_image_not_numpy_array(self):
        """Test crop_image with input that is not a numpy array."""
        self.assertIsNone(crop_image("not_an_image", (0,0,10,10)), "Should return None if image is not ndarray.")

    def test_crop_image_not_3_channel(self):
        """Test crop_image with input that is not a 3-channel image."""
        grayscale_image = np.random.randint(0, 256, size=(100, 150), dtype=np.uint8)
        self.assertIsNone(crop_image(grayscale_image, (0,0,10,10)), "Should return None if image is not 3-channel.")
        
        four_channel_image = np.random.randint(0, 256, size=(100, 150, 4), dtype=np.uint8)
        self.assertIsNone(crop_image(four_channel_image, (0,0,10,10)), "Should return None if image is not 3-channel (e.g. 4-channel).")


    def test_map_local_coords_to_global(self):
        """Test coordinate mapping from local to global."""
        local_box = (5, 10, 25, 35) # x1, y1, x2, y2 in cropped image
        crop_origin = (50, 100)     # x_offset, y_offset of crop from original
        
        expected_global_box = (
            local_box[0] + crop_origin[0], # 5 + 50 = 55
            local_box[1] + crop_origin[1], # 10 + 100 = 110
            local_box[2] + crop_origin[0], # 25 + 50 = 75
            local_box[3] + crop_origin[1]  # 35 + 100 = 135
        )
        
        global_box = map_local_coords_to_global(local_box, crop_origin)
        self.assertEqual(global_box, expected_global_box, "Global coordinates are not mapped correctly.")

    def test_map_local_coords_to_global_origin_at_zero(self):
        """Test mapping when crop origin is (0,0)."""
        local_box = (5, 10, 25, 35)
        crop_origin = (0, 0)
        # Expected global should be same as local
        global_box = map_local_coords_to_global(local_box, crop_origin)
        self.assertEqual(global_box, local_box, "Mapping with (0,0) origin should yield same coordinates.")

    # --- Tests for calculate_iou ---
    def test_calculate_iou_no_overlap(self):
        box1 = (0, 0, 10, 10)
        box2 = (20, 20, 30, 30)
        self.assertEqual(calculate_iou(box1, box2), 0.0, "Expected 0.0 IoU for non-overlapping boxes.")

    def test_calculate_iou_full_overlap_identical_boxes(self):
        box1 = (0, 0, 10, 10)
        box2 = (0, 0, 10, 10)
        self.assertEqual(calculate_iou(box1, box2), 1.0, "Expected 1.0 IoU for identical boxes.")

    def test_calculate_iou_partial_overlap(self):
        box1 = (0, 0, 10, 10) # Area = 100
        box2 = (5, 5, 15, 15) # Area = 100
        # Intersection: x_left=5, y_top=5, x_right=10, y_bottom=10. Area = (10-5)*(10-5) = 5*5 = 25
        # Union = Area1 + Area2 - Intersection = 100 + 100 - 25 = 175
        # IoU = 25 / 175 = 1/7
        expected_iou = 25.0 / (100.0 + 100.0 - 25.0)
        self.assertAlmostEqual(calculate_iou(box1, box2), expected_iou, places=7, msg="Incorrect IoU for partial overlap.")

    def test_calculate_iou_one_box_contains_another(self):
        box_outer = (0, 0, 20, 20)   # Area = 400
        box_inner = (5, 5, 15, 15)   # Area = 100
        # Intersection is box_inner area = 100
        # Union is box_outer area = 400
        # IoU = 100 / 400 = 0.25
        expected_iou = 100.0 / 400.0
        self.assertAlmostEqual(calculate_iou(box_outer, box_inner), expected_iou, places=7)
        self.assertAlmostEqual(calculate_iou(box_inner, box_outer), expected_iou, places=7, 
                               msg="IoU should be symmetric when one box contains another.")

    def test_calculate_iou_invalid_box(self):
        valid_box = (0, 0, 10, 10)
        invalid_box1 = (10, 10, 0, 0) # x1 > x2, y1 > y2
        invalid_box2 = (0, 0, 0, 10)  # zero width
        
        self.assertEqual(calculate_iou(valid_box, invalid_box1), 0.0, "IoU with invalid box (x1>x2) should be 0.")
        self.assertEqual(calculate_iou(invalid_box1, valid_box), 0.0, "IoU with invalid box (x1>x2) should be 0 (arg order).")
        self.assertEqual(calculate_iou(valid_box, invalid_box2), 0.0, "IoU with invalid box (zero width) should be 0.")
        self.assertEqual(calculate_iou(invalid_box1, invalid_box2), 0.0, "IoU between two invalid boxes should be 0.")

    def test_calculate_iou_edge_touch_no_overlap_area(self):
        box1 = (0, 0, 10, 10)
        box2 = (10, 0, 20, 10) # Touches at x=10 edge
        self.assertEqual(calculate_iou(box1, box2), 0.0, "Boxes touching at an edge should have 0 IoU.")
        
        box3 = (0, 10, 10, 20) # Touches at y=10 edge
        self.assertEqual(calculate_iou(box1, box3), 0.0, "Boxes touching at an edge should have 0 IoU.")

    # --- Tests for draw_detections_on_frame ---
    def test_draw_detections_on_frame_empty_detections(self):
        """Test drawing with an empty list of detections."""
        frame_copy = self.original_image.copy()
        drawn_frame = draw_detections_on_frame(self.original_image, [])
        self.assertTrue(np.array_equal(drawn_frame, frame_copy), 
                        "Should return an unaltered copy of the frame if no detections.")
        self.assertNotEqual(id(drawn_frame), id(self.original_image), "Should return a copy, not the original frame.")


    def test_draw_detections_on_frame_with_detections(self):
        """Test drawing with a list of detections."""
        detections = [
            {'class_name': 'person', 'confidence': 0.9, 'bounding_box': (10, 10, 60, 60)}, # x1,y1,x2,y2
            {'class_name': 'car', 'confidence': 0.8, 'bounding_box': (70, 70, 120, 95)}
        ]
        
        # Create a checksum or simple comparison metric before drawing
        original_sum = np.sum(self.original_image)
        
        drawn_frame = draw_detections_on_frame(self.original_image, detections)
        
        self.assertIsInstance(drawn_frame, np.ndarray, "Output should be a NumPy array.")
        self.assertEqual(drawn_frame.shape, self.original_image.shape, "Output shape should match input shape.")
        self.assertNotEqual(id(drawn_frame), id(self.original_image), "Should return a copy, not the original frame.")
        
        # Check if the image has changed. This is a basic check.
        # More sophisticated checks could involve looking for specific color pixels of boxes/text,
        # but that's brittle and complex for unit tests.
        drawn_sum = np.sum(drawn_frame)
        if self.original_image.size > 0 : # Avoid division by zero for empty images (though not expected here)
             # If original_sum is 0 (e.g. black image), any drawing will change it unless it draws black.
             # If original_sum is not 0, drawing should typically change it.
             # This check is not foolproof (e.g. drawing black on black, or colors that average out)
             # but for typical drawing on a non-monochromatic image, it's a reasonable heuristic.
            if original_sum == 0 and drawn_sum == 0 and detections: # e.g. black image, drawing black
                pass # Can't reliably tell if drawing happened by sum alone
            else:
                 # A more robust check for typical cases:
                 # If any pixel changed, the arrays won't be equal.
                self.assertFalse(np.array_equal(drawn_frame, self.original_image),
                                 "Drawing detections should alter the frame's pixel data.")
        
    def test_draw_detections_on_frame_invalid_frame_input(self):
        """Test with invalid frame input."""
        detections = [{'class_name': 'person', 'confidence': 0.9, 'bounding_box': (10,10,60,60)}]
        invalid_frame = "not_a_numpy_array"
        # The function currently prints an error and returns the input.
        # Depending on strictness, one might expect it to raise an error or return None.
        # Based on current implementation:
        returned_frame = draw_detections_on_frame(invalid_frame, detections)
        self.assertEqual(returned_frame, invalid_frame, "Should return the invalid input as per current error handling.")

    def test_draw_detections_on_frame_detection_missing_fields(self):
        """Test with detections that are missing required fields (e.g., bounding_box)."""
        # Detections missing 'bounding_box' should be skipped but not crash.
        detections_malformed = [
            {'class_name': 'person', 'confidence': 0.9}, # Missing bounding_box
            {'class_name': 'car', 'confidence': 0.8, 'bounding_box': (10,10,50,50)} # Valid one
        ]
        original_sum = np.sum(self.original_image)
        drawn_frame = draw_detections_on_frame(self.original_image, detections_malformed)
        
        # It should have drawn the valid detection.
        # This means the frame should be different from original if the valid detection was drawn.
        self.assertFalse(np.array_equal(drawn_frame, self.original_image),
                         "Frame should be altered by the valid detection, malformed one skipped.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
