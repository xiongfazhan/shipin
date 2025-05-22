import numpy as np

def crop_image(image: np.ndarray, crop_box: tuple[int, int, int, int]) -> np.ndarray | None:
    """
    Crops an image using the provided bounding box.

    Args:
        image (np.ndarray): The original image (NumPy array).
        crop_box (tuple[int, int, int, int]): A tuple (x1, y1, x2, y2)
                                              defining the cropping region.
                                              Coordinates are absolute.

    Returns:
        np.ndarray | None: The cropped image region as a NumPy array, 
                           or None if crop_box is invalid or outside image bounds.
    """
    if not isinstance(image, np.ndarray):
        print("Error: Input image is not a NumPy array.")
        return None
    if image.ndim != 3 or image.shape[2] != 3:
        print(f"Error: Input image is not a 3-channel image. Shape: {image.shape}")
        return None

    img_height, img_width = image.shape[:2]
    x1, y1, x2, y2 = crop_box

    # Basic validation of crop box coordinates
    if not all(isinstance(coord, int) for coord in crop_box):
        print(f"Error: Crop box coordinates must be integers. Got: {crop_box}")
        return None
        
    if x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
        print(f"Warning: Crop box {crop_box} is partially or fully outside image dimensions ({img_width}x{img_height}). Clamping to image bounds.")
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(img_width, x2)
        y2 = min(img_height, y2)

    if x1 >= x2 or y1 >= y2:
        print(f"Error: Invalid crop box dimensions after clamping. x1 >= x2 or y1 >= y2. Box: ({x1},{y1},{x2},{y2})")
        return None
        
    try:
        cropped = image[y1:y2, x1:x2]
        if cropped.size == 0:
            print(f"Warning: Crop operation with box {crop_box} (clamped: ({x1},{y1},{x2},{y2})) resulted in an empty image.")
            return None
        return cropped
    except Exception as e:
        print(f"Error during image cropping with box {crop_box}: {e}")
        return None

def map_local_coords_to_global(
    local_box: tuple[int, int, int, int], 
    crop_origin: tuple[int, int]
) -> tuple[int, int, int, int]:
    """
    Maps a bounding box from local (cropped image) coordinates to global 
    (original image) coordinates.

    Args:
        local_box (tuple[int, int, int, int]): Bounding box (x1, y1, x2, y2)
                                               from the detection on the cropped image.
        crop_origin (tuple[int, int]): The top-left coordinate (global_x_offset, global_y_offset)
                                       of where the crop started in the original image.

    Returns:
        tuple[int, int, int, int]: The bounding box coordinates mapped back to the
                                   original image's coordinate system.
    """
    local_x1, local_y1, local_x2, local_y2 = local_box
    global_x_offset, global_y_offset = crop_origin

    global_x1 = local_x1 + global_x_offset
    global_y1 = local_y1 + global_y_offset
    global_x2 = local_x2 + global_x_offset
    global_y2 = local_y2 + global_y_offset

    return (global_x1, global_y1, global_x2, global_y2)

if __name__ == '__main__':
    print("Running Image Utils Example...")

    # Create a dummy image for testing
    # Typically, you'd use OpenCV (cv2) for image operations, but let's stick to NumPy for simplicity here.
    dummy_original_image = np.random.randint(0, 256, size=(100, 150, 3), dtype=np.uint8)
    print(f"Created a dummy image of shape: {dummy_original_image.shape}")

    # --- Test crop_image ---
    print("\n--- Testing crop_image ---")
    valid_crop_box = (10, 20, 50, 70) # x1, y1, x2, y2
    cropped_section = crop_image(dummy_original_image, valid_crop_box)
    if cropped_section is not None:
        # Expected shape: height = y2-y1 = 50, width = x2-x1 = 40
        print(f"Cropped section with box {valid_crop_box}. Shape: {cropped_section.shape} (Expected: (50, 40, 3))")
        assert cropped_section.shape == (50, 40, 3)
    else:
        print(f"Cropping with {valid_crop_box} failed.")

    invalid_crop_box_dims = (50, 70, 10, 20) # x1 > x2
    cropped_invalid = crop_image(dummy_original_image, invalid_crop_box_dims)
    if cropped_invalid is None:
        print(f"Cropping with invalid box {invalid_crop_box_dims} correctly returned None.")
    else:
        print(f"Cropping with invalid box {invalid_crop_box_dims} unexpectedly returned an image.")

    # Box partially outside, should be clamped
    partially_outside_box = (-10, -10, 50, 50) # x1,y1 <0
    cropped_clamped = crop_image(dummy_original_image, partially_outside_box)
    if cropped_clamped is not None:
        # Expected clamped box: (0,0,50,50). Shape: (50,50,3)
        print(f"Cropped with partially outside box {partially_outside_box}. Clamped shape: {cropped_clamped.shape} (Expected: (50,50,3))")
        assert cropped_clamped.shape == (50, 50, 3)
    else:
        print(f"Cropping with {partially_outside_box} (expecting clamping) failed.")
    
    # Box fully outside
    fully_outside_box = (200, 200, 250, 250)
    cropped_fully_outside = crop_image(dummy_original_image, fully_outside_box)
    if cropped_fully_outside is None:
        print(f"Cropping with fully outside box {fully_outside_box} correctly returned None.")
    else:
        print(f"Cropping with fully outside box {fully_outside_box} unexpectedly returned an image: {cropped_fully_outside.shape}")


    # --- Test map_local_coords_to_global ---
    print("\n--- Testing map_local_coords_to_global ---")
    local_detection_box = (5, 10, 25, 30) # x1, y1, x2, y2 within the cropped image
    # Assume the crop_box used to get the local_detection_box was (10, 20, 50, 70) from original
    # So, the origin of the crop (top-left corner) is (10, 20)
    crop_origin_coords = (valid_crop_box[0], valid_crop_box[1]) # (10, 20)
    
    global_coords = map_local_coords_to_global(local_detection_box, crop_origin_coords)
    # Expected:
    # global_x1 = 5 + 10 = 15
    # global_y1 = 10 + 20 = 30
    # global_x2 = 25 + 10 = 35
    # global_y2 = 30 + 20 = 50
    expected_global_coords = (15, 30, 35, 50)
    print(f"Local box: {local_detection_box}, Crop origin: {crop_origin_coords}")
    print(f"Mapped to Global: {global_coords} (Expected: {expected_global_coords})")
    assert global_coords == expected_global_coords

    print("\nImage Utils Example finished.")


def calculate_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    """
    Calculates the Intersection over Union (IoU) between two bounding boxes.

    Args:
        box1 (tuple[int, int, int, int]): Bounding box (x1, y1, x2, y2).
        box2 (tuple[int, int, int, int]): Bounding box (x1, y1, x2, y2).

    Returns:
        float: The IoU score, between 0.0 and 1.0. Returns 0.0 if there is no overlap
               or if either box is invalid (e.g., x1 >= x2).
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2

    # Validate boxes
    if x1_1 >= x2_1 or y1_1 >= y2_1 or x1_2 >= x2_2 or y1_2 >= y2_2:
        return 0.0

    # Calculate the coordinates of the intersection rectangle
    x_left = max(x1_1, x1_2)
    y_top = max(y1_1, y1_2)
    x_right = min(x2_1, x2_2)
    y_bottom = min(y2_1, y2_2)

    # If there is no overlap, return 0.0
    if x_right < x_left or y_bottom < y_top:
        return 0.0

    # Calculate the area of intersection
    intersection_area = (x_right - x_left) * (y_bottom - y_top)

    # Calculate the area of both bounding boxes
    area_box1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area_box2 = (x2_2 - x1_2) * (y2_2 - y1_2)

    # Calculate the IoU
    iou = intersection_area / float(area_box1 + area_box2 - intersection_area)
    
    return iou

import cv2 # Import OpenCV for drawing

def draw_detections_on_frame(frame: np.ndarray, detections: list[dict]) -> np.ndarray:
    """
    Draws bounding boxes and labels for detections on a frame.

    Args:
        frame (np.ndarray): The original image/frame (NumPy array).
        detections (list[dict]): A list of detection dictionaries, each containing
                                 'class_name', 'confidence', and 'bounding_box'.

    Returns:
        np.ndarray: A copy of the frame with detections drawn on it.
    """
    if not isinstance(frame, np.ndarray):
        print("Error (draw_detections_on_frame): Input frame is not a NumPy array.")
        return frame # Or raise error

    output_frame = frame.copy() # Work on a copy

    if not detections:
        return output_frame # Return copy if no detections

    # Basic color: Green for box, White for text. Can be expanded.
    box_color = (0, 255, 0)  # BGR for OpenCV
    text_color = (255, 255, 255) # BGR
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1
    label_offset = 5 # Offset for text from the top of the box

    for detection in detections:
        try:
            class_name = detection.get('class_name', 'Unknown')
            confidence = detection.get('confidence', 0.0)
            box = detection.get('bounding_box')

            if not box or len(box) != 4:
                print(f"Warning (draw_detections_on_frame): Skipping detection with invalid box: {detection}")
                continue

            x1, y1, x2, y2 = map(int, box) # Ensure integer coordinates

            # Draw the rectangle
            cv2.rectangle(output_frame, (x1, y1), (x2, y2), box_color, 2) # Thickness 2

            # Prepare the label text
            label = f"{class_name}: {confidence:.2f}"

            # Get text size to position it nicely
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)
            
            # Position text: above the box, or inside if y1 is too small
            label_y_pos = y1 - label_offset
            if label_y_pos < text_height: # If text would go off-screen (top)
                label_y_pos = y1 + text_height + label_offset # Put it inside, below top edge
                if label_y_pos > y2: # If also too low, adjust (e.g. center or clip)
                    label_y_pos = y1 + (y2-y1)//2 # Simple vertical center if box is too small
            
            # Optional: Draw a filled rectangle behind the text for better readability
            # cv2.rectangle(output_frame, (x1, label_y_pos - text_height - baseline//2), 
            #               (x1 + text_width, label_y_pos + baseline//2), box_color, -1) # Filled

            # Put the text
            cv2.putText(output_frame, label, (x1, label_y_pos), font, font_scale, text_color, font_thickness, lineType=cv2.LINE_AA)

        except Exception as e:
            print(f"Error drawing a detection ({detection}): {e}")
            # Continue to next detection
            
    return output_frame
