import numpy as np
import sys
import os

# Adjust path to import from parent directory (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from processing_core.yolo_detector import YOLODetector
from utils.image_utils import crop_image, map_local_coords_to_global

DEFAULT_LOCAL_TARGET_CLASSES = ['desk', 'table', 'laptop', 'tv', 'remote', 'sofa', 'bed', 'chair'] # Expanded list

class AdvancedDetector:
    """
    Handles a two-stage detection logic: initial detection on the whole frame,
    then focused detection on areas of interest (local targets).
    """
    def __init__(self, 
                 yolo_detector: YOLODetector, 
                 local_target_classes: list[str] = None, 
                 local_target_confidence_threshold: float = 0.4, # Adjusted threshold slightly
                 # Parameters for final filtering stage
                 min_confidence_filter: float = 0.5,
                 allowed_classes_filter: list[str] | None = None, # None means allow all
                 merge_iou_threshold: float = 0.5,
                 class_specific_nms: bool = True):
        """
        Initializes the AdvancedDetector.

        Args:
            yolo_detector (YOLODetector): An instance of YOLODetector for performing detections.
            local_target_classes (list[str], optional): List of class names to be considered as
                                                        local targets. Defaults to DEFAULT_LOCAL_TARGET_CLASSES.
            local_target_confidence_threshold (float, optional): Minimum confidence for an object
                                                                 to be considered a local target.
                                                                 Defaults to 0.4.
        """
        if not isinstance(yolo_detector, YOLODetector):
            raise ValueError("yolo_detector must be an instance of YOLODetector.")
        
        self.yolo_detector = yolo_detector
        self.local_target_classes = local_target_classes if local_target_classes is not None else DEFAULT_LOCAL_TARGET_CLASSES
        self.local_target_confidence_threshold = local_target_confidence_threshold
        
        # Store filter parameters
        self.min_confidence_filter = min_confidence_filter
        self.allowed_classes_filter = allowed_classes_filter # Can be None
        self.merge_iou_threshold = merge_iou_threshold
        self.class_specific_nms = class_specific_nms
        
        print(f"AdvancedDetector initialized with local target classes: {self.local_target_classes}, "
              f"conf_thresh: {self.local_target_confidence_threshold}, "
              f"filter_conf: {self.min_confidence_filter}, filter_classes: {self.allowed_classes_filter}, "
              f"merge_iou: {self.merge_iou_threshold}, class_specific_nms: {self.class_specific_nms}")

    def detect_with_localization(self, frame: np.ndarray, filter_config_override: dict | None = None) -> list[dict]:
        """
        Performs two-stage detection: initial scan, then detailed scan on local target areas.

        Args:
            frame (np.ndarray): The input image frame (NumPy array).

        Returns:
            list[dict]: A list of all detections, including initial ones and re-mapped
                        secondary detections from local target areas. Duplicates may be present.
        """
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            print("Error: Input frame must be a 3-channel NumPy array.")
            return []

        print(f"\nAdvancedDetector: Starting detection on frame of shape {frame.shape}")
        
        # 1. Perform initial detection on the whole frame
        initial_detection_results = self.yolo_detector.detect_objects([frame])
        if not initial_detection_results: # Should return [[]] if frame is bad, or actual error
            print("AdvancedDetector: Initial detection failed or returned no results.")
            return []
        
        initial_detections = initial_detection_results[0] # Results for the single frame
        print(f"AdvancedDetector: Initial detection found {len(initial_detections)} objects.")

        # Initialize all_raw_detections with a copy of initial_detections
        all_raw_detections = list(initial_detections) 

        # 2. Iterate through initial detections to find local targets
        for i_det, detection in enumerate(initial_detections):
            class_name = detection.get('class_name')
            confidence = detection.get('confidence', 0.0)
            
            # Check if this detection qualifies as a local target
            if class_name in self.local_target_classes and \
               confidence >= self.local_target_confidence_threshold:
                
                target_crop_box = detection.get('bounding_box')
                if not target_crop_box or len(target_crop_box) != 4:
                    print(f"Warning: Skipping local target '{class_name}' due to missing/invalid bounding box: {target_crop_box}")
                    continue

                print(f"AdvancedDetector: Found local target '{class_name}' (Conf: {confidence:.2f}) "
                      f"at box {target_crop_box}. Proceeding to secondary scan.")

                # 3. Crop the original frame using the target_crop_box
                # Ensure crop_box is (x1, y1, x2, y2)
                # YOLODetector returns (x1,y1,x2,y2) so it should be fine.
                cropped_image = crop_image(frame, target_crop_box)

                if cropped_image is None or cropped_image.size == 0:
                    print(f"AdvancedDetector: Cropping for local target '{class_name}' at {target_crop_box} failed or resulted in empty image. Skipping secondary scan for this target.")
                    continue
                
                print(f"AdvancedDetector: Cropped image for secondary scan. Shape: {cropped_image.shape}")

                # 4. Perform secondary YOLO detection on the cropped_image
                secondary_detection_results = self.yolo_detector.detect_objects([cropped_image])
                if not secondary_detection_results:
                    print(f"AdvancedDetector: Secondary detection on cropped image for '{class_name}' failed or returned no results.")
                    continue
                
                secondary_detections_on_crop = secondary_detection_results[0] # Results for the single cropped image
                print(f"AdvancedDetector: Secondary scan on '{class_name}' crop found {len(secondary_detections_on_crop)} objects.")

                # 5. Process secondary detections
                crop_origin = (target_crop_box[0], target_crop_box[1]) # (global_x_offset, global_y_offset)
                for sec_det in secondary_detections_on_crop:
                    local_box = sec_det.get('bounding_box')
                    if not local_box or len(local_box) != 4:
                        print(f"Warning: Skipping secondary detection due to missing/invalid local_box: {local_box}")
                        continue
                        
                    # Map local bounding_box to global coordinates
                    global_box = map_local_coords_to_global(local_box, crop_origin)
                    
                    # Create a new detection dictionary or update existing (safer to create new)
                    # to avoid modifying original list items if they are referenced elsewhere.
                    # However, here we are adding to final_detections, so a new dict is good.
                    remapped_detection = sec_det.copy() # Keep all other info like class, confidence
                    remapped_detection['bounding_box'] = global_box
                    remapped_detection['source'] = 'secondary_scan' # Optional: add source info
                    
                    all_raw_detections.append(remapped_detection)
                    print(f"AdvancedDetector: Added secondary detection: {remapped_detection['class_name']} at global box {global_box}")

        print(f"AdvancedDetector: Total raw detections before merge/filter: {len(all_raw_detections)}")

        # 6. Merge and Filter detections
        # Assuming result_processor is imported correctly
        from . import result_processor # Relative import if in the same package

        merged_detections = result_processor.merge_detections(
            all_raw_detections, 
            iou_threshold=self.merge_iou_threshold,
            class_specific_nms=self.class_specific_nms
        )
        
        # Define a filter_config
        current_filter_config = { 
            'min_confidence': self.min_confidence_filter,
            'allowed_classes': self.allowed_classes_filter,
            'max_detections_per_frame': None # Not implementing max_detections_per_frame limit here yet
        }
        # Allow overriding filter config per call if provided
        if filter_config_override:
            current_filter_config.update(filter_config_override)
            print(f"AdvancedDetector: Using overridden filter config: {current_filter_config}")
            
        filtered_detections = result_processor.filter_detections(merged_detections, current_filter_config)
        
        print(f"AdvancedDetector: Final filtered detections: {len(filtered_detections)}")
        return filtered_detections

if __name__ == '__main__':
    print("Running AdvancedDetector Example...")
    
    # This example requires a YOLODetector instance and potentially an image.
    # We'll use a dummy YOLODetector and dummy frames for simplicity in this standalone example.
    
    # Mock YOLODetector and its outputs for this example
    class MockYOLODetector(YOLODetector):
        def __init__(self, model_name: str = 'mock_model.pt'):
            self.model_name = model_name
            self.model = "mock_model_loaded" # Simulate a loaded model
            print(f"MockYOLODetector initialized with {model_name}")

        def detect_objects(self, frames: list[np.ndarray]) -> list[list[dict]]:
            all_frames_detections = []
            for frame_idx, frame in enumerate(frames):
                frame_detections = []
                # Simulate different detections based on frame "content" (e.g., shape or a known pattern)
                # This is a very basic simulation.
                
                # If it's the "main" frame (assume larger size)
                if frame.shape == (480, 640, 3): 
                    print("MockYOLO: Simulating initial detection on main frame.")
                    # Simulate detecting a 'desk' (local target) and a 'cup'
                    frame_detections.append({
                        'class_id': 0, 'class_name': 'desk', 
                        'bounding_box': (50, 100, 350, 300), # x1, y1, x2, y2
                        'confidence': 0.85
                    })
                    frame_detections.append({
                        'class_id': 1, 'class_name': 'cup', 
                        'bounding_box': (100, 150, 150, 200), 
                        'confidence': 0.70
                    })
                # If it's a "cropped" frame (assume smaller size, e.g., the desk crop)
                # (50,100,350,300) -> width=300, height=200
                elif frame.shape == (200, 300, 3): 
                    print("MockYOLO: Simulating secondary detection on cropped 'desk' area.")
                    # Simulate detecting a 'laptop' on the desk
                    frame_detections.append({
                        'class_id': 2, 'class_name': 'laptop', 
                        'bounding_box': (20, 30, 120, 130), # Coords relative to cropped image
                        'confidence': 0.90
                    })
                    frame_detections.append({ # Another object on the desk
                        'class_id': 3, 'class_name': 'mouse', 
                        'bounding_box': (150, 80, 180, 110), 
                        'confidence': 0.75
                    })
                else:
                    print(f"MockYOLO: No specific mock detections for frame shape {frame.shape}")

                all_frames_detections.append(frame_detections)
            return all_frames_detections

    # 1. Initialize Mock YOLODetector
    mock_yolo = MockYOLODetector()

    # 2. Initialize AdvancedDetector with the mock YOLO detector
    # Using default local target classes which include 'desk'
    # And default filter parameters
    advanced_detector = AdvancedDetector(
        yolo_detector=mock_yolo,
        min_confidence_filter=0.5, # Example for testing main
        allowed_classes_filter=['desk', 'cup', 'laptop', 'mouse'] # Example for testing main
    )

    # 3. Create a dummy main frame
    main_frame = np.zeros((480, 640, 3), dtype=np.uint8) # Dimensions used in mock
    print(f"\nCreated a dummy main frame of shape: {main_frame.shape}")

    # 4. Perform detection with localization
    final_processed_results = advanced_detector.detect_with_localization(main_frame)

    # 5. Print results
    print("\n--- Advanced Detection Results (After Merge & Filter) ---")
    if final_processed_results:
        for i, det in enumerate(final_processed_results):
            # Source might be lost after NMS if NMS picks one over the other and doesn't preserve/combine source
            # The current NMS keeps the original dict of the winner.
            source_info = f"(Source: {det.get('source', 'initial')})" if 'source' in det else ""
            print(f"Detection {i+1} {source_info}:")
            print(f"  Class: {det['class_name']} (ID: {det.get('class_id', 'N/A')}), "
                  f"Confidence: {det.get('confidence', 0.0):.4f}, BBox: {det.get('bounding_box')}")
    else:
        print("No detections returned by AdvancedDetector after processing.")

    # Expected logic:
    # - Initial scan finds 'desk' and 'cup'.
    # - 'desk' is a local target. Area (50,100,350,300) is cropped.
    #   Crop origin is (50, 100). Cropped image size is height=200, width=300.
    # - Secondary scan on this 200x300 crop finds 'laptop' at (20,30,120,130) [local].
    #   This 'laptop' box is mapped to global:
    #   gx1 = 20 + 50 = 70
    #   gy1 = 30 + 100 = 130
    #   gx2 = 120 + 50 = 170
    #   gy2 = 130 + 100 = 230
    #   Global 'laptop' box: (70, 130, 170, 230), conf 0.90
    # - Secondary scan also finds 'mouse' at (150,80,180,110) [local].
    #   Mapped to global: (200, 180, 230, 210), conf 0.75
    #
    # Raw Detections before merge/filter (4 total):
    # 1. desk (0.85)
    # 2. cup (0.70)
    # 3. laptop (0.90) (remapped)
    # 4. mouse (0.75) (remapped)
    #
    # Merge: Assuming no overlaps among these 4 that would cause NMS suppression with typical IoU.
    # Filter (min_conf=0.5, allowed=['desk','cup','laptop','mouse']): All 4 should pass.
    # Expected final: 4 detections.
    #
    # If, for example, min_confidence_filter was 0.8:
    # desk (0.85), laptop (0.90) would pass. Cup (0.70) and mouse (0.75) would be filtered.
    #
    # If allowed_classes_filter was ['desk', 'laptop']:
    # desk (0.85), laptop (0.90) would pass. Cup and mouse would be filtered.

    print("\nAdvancedDetector Example finished.")
