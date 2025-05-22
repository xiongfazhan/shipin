import sys
import os

# Adjust path to import from parent directory (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from utils.image_utils import calculate_iou # Assuming calculate_iou is in image_utils.py

def merge_detections(all_detections: list[dict], iou_threshold: float = 0.5, class_specific_nms: bool = True) -> list[dict]:
    """
    Merges overlapping detections using Non-Maximum Suppression (NMS).

    Args:
        all_detections (list[dict]): A list of detection dictionaries.
            Each dict must have 'bounding_box', 'confidence', and 'class_name' (if class_specific_nms).
        iou_threshold (float): IoU threshold for suppressing detections.
        class_specific_nms (bool): If True, NMS is applied per class. If False, NMS is applied
                                   globally across all classes.

    Returns:
        list[dict]: A list of merged detection dictionaries.
    """
    if not all_detections:
        return []

    # Sort detections by confidence in descending order.
    # Make a copy to avoid modifying the original list if it's passed by reference elsewhere.
    detections_sorted = sorted(list(all_detections), key=lambda x: x.get('confidence', 0.0), reverse=True)

    merged_results = []
    
    # If class-specific NMS, process each class separately
    if class_specific_nms:
        # Group detections by class name
        detections_by_class = {}
        for det in detections_sorted:
            class_name = det.get('class_name', 'unknown_class') # Default if class_name is missing
            if class_name not in detections_by_class:
                detections_by_class[class_name] = []
            detections_by_class[class_name].append(det)
        
        # Apply NMS for each class
        for class_name, class_detections in detections_by_class.items():
            # class_detections are already sorted by confidence due to the initial sort
            
            # List to keep track of detections for this class to process
            # (we remove from this list as we go)
            current_class_detections_to_process = list(class_detections) 
            
            while current_class_detections_to_process:
                # Pick the detection with the highest confidence (it's the first one)
                highest_conf_det = current_class_detections_to_process.pop(0)
                merged_results.append(highest_conf_det)
                
                # Compare with remaining detections for this class
                remaining_for_class_after_pick = []
                for other_det in current_class_detections_to_process:
                    iou = calculate_iou(highest_conf_det['bounding_box'], other_det['bounding_box'])
                    if iou < iou_threshold:
                        remaining_for_class_after_pick.append(other_det)
                    # else: it's suppressed (IoU >= threshold)
                
                current_class_detections_to_process = remaining_for_class_after_pick
    
    # If global NMS (not class-specific)
    else:
        detections_to_process_global = list(detections_sorted)
        while detections_to_process_global:
            highest_conf_det = detections_to_process_global.pop(0)
            merged_results.append(highest_conf_det)

            remaining_global_after_pick = []
            for other_det in detections_to_process_global:
                iou = calculate_iou(highest_conf_det['bounding_box'], other_det['bounding_box'])
                if iou < iou_threshold:
                    remaining_global_after_pick.append(other_det)
            detections_to_process_global = remaining_global_after_pick
            
    # Re-sort merged_results by confidence as NMS might alter order if processed by class
    # and then appended. Though, if appended class by class, order within class is preserved.
    # A final sort ensures overall highest confidence detections come first if desired.
    # This is optional and depends on desired output order.
    # merged_results_sorted_final = sorted(merged_results, key=lambda x: x.get('confidence', 0.0), reverse=True)

    print(f"Merge Detections: Input {len(all_detections)} -> Output {len(merged_results)} (IoU: {iou_threshold}, Class-Specific: {class_specific_nms})")
    return merged_results


def filter_detections(detections: list[dict], config: dict) -> list[dict]:
    """
    Filters detections based on provided criteria.

    Args:
        detections (list[dict]): A list of detection dictionaries.
        config (dict): A dictionary specifying filtering criteria.
            Example: {
                'min_confidence': 0.6,
                'allowed_classes': ['person', 'car'], # None or empty means all classes allowed
                'max_detections_per_frame': 20 # None means no limit
            }

    Returns:
        list[dict]: The filtered list of detections.
    """
    if not detections:
        return []

    filtered_results = list(detections) # Start with a copy

    # 1. Filter by min_confidence
    min_confidence = config.get('min_confidence')
    if min_confidence is not None:
        if not isinstance(min_confidence, (float, int)) or min_confidence < 0 or min_confidence > 1:
            print(f"Warning (filter_detections): Invalid min_confidence value '{min_confidence}'. Must be float between 0 and 1. Skipping confidence filter.")
        else:
            filtered_results = [
                det for det in filtered_results 
                if det.get('confidence', 0.0) >= min_confidence
            ]
            print(f"Filter Detections: After min_confidence ({min_confidence}), {len(filtered_results)} detections remain.")


    # 2. Filter by allowed_classes
    allowed_classes = config.get('allowed_classes')
    if allowed_classes is not None: # Check if key exists
        if isinstance(allowed_classes, list) and len(allowed_classes) > 0:
            allowed_classes_set = set(allowed_classes) # For efficient lookup
            filtered_results = [
                det for det in filtered_results
                if det.get('class_name') in allowed_classes_set
            ]
            print(f"Filter Detections: After allowed_classes ({allowed_classes}), {len(filtered_results)} detections remain.")
        elif isinstance(allowed_classes, list) and len(allowed_classes) == 0:
            # Empty list means keep all classes, so no filtering needed here
            print(f"Filter Detections: 'allowed_classes' is empty, all classes kept.")
            pass 
        else:
            print(f"Warning (filter_detections): Invalid 'allowed_classes' value '{allowed_classes}'. Must be a list of strings. Skipping class filter.")


    # 3. Apply max_detections_per_frame
    # This usually implies keeping the highest confidence ones.
    # Detections should ideally be sorted by confidence before this step if not already.
    max_detections = config.get('max_detections_per_frame')
    if max_detections is not None:
        if not isinstance(max_detections, int) or max_detections < 0:
            print(f"Warning (filter_detections): Invalid 'max_detections_per_frame' value '{max_detections}'. Must be a non-negative integer. Skipping this limit.")
        else:
            if len(filtered_results) > max_detections:
                # Sort by confidence to keep the top N. Assuming higher confidence is better.
                # The input `detections` to this function might already be sorted from NMS.
                # If not, or to be sure:
                filtered_results_sorted_for_max = sorted(filtered_results, key=lambda x: x.get('confidence', 0.0), reverse=True)
                filtered_results = filtered_results_sorted_for_max[:max_detections]
                print(f"Filter Detections: After max_detections_per_frame ({max_detections}), {len(filtered_results)} detections remain.")

    print(f"Filter Detections: Final output {len(filtered_results)} detections.")
    return filtered_results


if __name__ == '__main__':
    print("Running Result Processor Example...")

    # Sample detections (normally from AdvancedDetector)
    sample_raw_detections = [
        # Object 1: A prominent person
        {'class_id': 0, 'class_name': 'person', 'bounding_box': (50, 50, 150, 250), 'confidence': 0.95, 'source': 'initial'},
        # Object 2: Another person, highly overlapping with person 1, lower confidence
        {'class_id': 0, 'class_name': 'person', 'bounding_box': (60, 60, 160, 260), 'confidence': 0.85, 'source': 'initial'},
        # Object 3: A car, distinct
        {'class_id': 2, 'class_name': 'car', 'bounding_box': (200, 100, 300, 200), 'confidence': 0.90, 'source': 'initial'},
        # Object 4: A bicycle, some overlap with car, but different class
        {'class_id': 1, 'class_name': 'bicycle', 'bounding_box': (280, 110, 380, 220), 'confidence': 0.70, 'source': 'secondary'},
        # Object 5: Another car, low confidence, overlapping with car 3
        {'class_id': 2, 'class_name': 'car', 'bounding_box': (210, 105, 310, 205), 'confidence': 0.50, 'source': 'secondary'},
        # Object 6: A very low confidence person
        {'class_id': 0, 'class_name': 'person', 'bounding_box': (400, 50, 450, 150), 'confidence': 0.30, 'source': 'initial'},
        # Object 7: A high confidence cat (not in typical allowed_classes for some configs)
        {'class_id': 15, 'class_name': 'cat', 'bounding_box': (500, 200, 580, 280), 'confidence': 0.92, 'source': 'initial'},
    ]

    print(f"\nInitial raw detections: {len(sample_raw_detections)}")
    for det in sample_raw_deteCTIONS: print(f"  {det}")

    # --- Test merge_detections ---
    print("\n--- Testing merge_detections (IoU=0.5, Class-Specific=True) ---")
    # Expected: Person 2 (overlap with 1, lower conf) and Car 5 (overlap with 3, lower conf) should be removed.
    # Bicycle should remain as it's different class than car 3, even if they overlap.
    merged = merge_detections(sample_raw_detections, iou_threshold=0.5, class_specific_nms=True)
    print(f"Merged detections (class-specific NMS): {len(merged)}")
    for det in merged: print(f"  {det}")
    # Expected: Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Person 6 (0.30), Cat (0.92) = 5 detections

    print("\n--- Testing merge_detections (IoU=0.5, Class-Specific=False/Global NMS) ---")
    # Global NMS: If bicycle (0.70) overlaps car 3 (0.90) significantly, car 3 (higher conf) might suppress bicycle.
    # Let's calculate IoU for car (200,100,300,200) and bicycle (280,110,380,220)
    # Intersection: x_left=280, y_top=110, x_right=300, y_bottom=200. Area = (300-280)*(200-110) = 20*90 = 1800
    # Area car: 100*100 = 10000. Area bicycle: 100*110 = 11000.
    # IoU = 1800 / (10000 + 11000 - 1800) = 1800 / (21000 - 1800) = 1800 / 19200 approx 0.09. Low.
    # So, bicycle should NOT be suppressed by car 3 even in global NMS with IoU 0.5.
    merged_global = merge_detections(sample_raw_detections, iou_threshold=0.5, class_specific_nms=False)
    print(f"Merged detections (global NMS): {len(merged_global)}")
    for det in merged_global: print(f"  {det}")
    # Expected: Same as class-specific in this case, as inter-class IoU is low. 5 detections.


    # --- Test filter_detections ---
    # Using 'merged' from class-specific NMS as input
    print("\n--- Testing filter_detections ---")
    filter_config_example = {
        'min_confidence': 0.65,
        'allowed_classes': ['person', 'car'], # Cat and Bicycle should be filtered out
        'max_detections_per_frame': 3 
    }
    print(f"Using filter config: {filter_config_example}")
    # Input to filter (from class-specific NMS, 5 detections):
    # Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Person 6 (0.30), Cat (0.92)
    # After min_confidence 0.65: Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Cat (0.92) -> 4 detections
    # After allowed_classes ['person', 'car']: Person 1 (0.95), Car 3 (0.90) -> 2 detections
    # After max_detections 3: No change as already 2.
    # Final expected: Person 1 (0.95), Car 3 (0.90)
    
    filtered = filter_detections(merged, filter_config_example)
    print(f"Filtered detections: {len(filtered)}")
    for det in filtered: print(f"  {det}")

    print("\n--- Testing filter_detections (empty allowed_classes, no max_detections) ---")
    filter_config_example_2 = {
        'min_confidence': 0.5, # Person 6 (0.30) should be filtered out
        'allowed_classes': [], # Keep all classes
        'max_detections_per_frame': None
    }
    print(f"Using filter config: {filter_config_example_2}")
    # Input: Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Person 6 (0.30), Cat (0.92)
    # After min_confidence 0.5: Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Cat (0.92) -> 4 detections
    # Allowed_classes empty: No change.
    # Max_detections None: No change.
    # Final expected: Person 1 (0.95), Car 3 (0.90), Bicycle (0.70), Cat (0.92)
    
    filtered_2 = filter_detections(merged, filter_config_example_2)
    print(f"Filtered detections (config 2): {len(filtered_2)}")
    for det in filtered_2: print(f"  {det}")
    
    print("\nResult Processor Example finished.")
