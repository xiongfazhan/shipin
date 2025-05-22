import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results # For type hinting
import os

class YOLODetector:
    """
    A class for performing object detection using a YOLO model from Ultralytics.
    """
    def __init__(self, model_name: str = 'yolov8n.pt'):
        """
        Initializes the YOLODetector.

        Args:
            model_name (str): The name of the YOLO model to load (e.g., 'yolov8n.pt').
                              The model will be downloaded if not available locally and
                              internet connection is present.
        """
        self.model_name = model_name
        self.model = None
        try:
            print(f"Loading YOLO model: {self.model_name}...")
            self.model = YOLO(self.model_name)
            # Perform a dummy inference to ensure model is fully loaded/initialized,
            # especially for models that might be downloaded.
            # Create a small dummy image (e.g., 32x32 black image)
            dummy_image = np.zeros((32, 32, 3), dtype=np.uint8)
            self.model(dummy_image, verbose=False) # verbose=False to reduce console output
            print(f"YOLO model '{self.model_name}' loaded successfully.")
        except Exception as e:
            print(f"Error loading YOLO model '{self.model_name}': {e}")
            # Depending on requirements, could raise error or set self.model to None
            # For now, we'll let it be None and handle in detect_objects
            # raise e # Or handle more gracefully

    def detect_objects(self, frames: list[np.ndarray]) -> list[list[dict]]:
        """
        Performs object detection on a list of frames.

        Args:
            frames (list[np.ndarray]): A list of frames (as NumPy arrays).

        Returns:
            list[list[dict]]: A list of lists of dictionaries. Each inner list
                              corresponds to a frame and contains dictionaries for
                              each detected object.
                              Example: [ [detection1_frame1, detection2_frame1], [detection1_frame2], [] ]
        """
        all_frames_detections = []

        if self.model is None:
            print("Error: YOLO model is not loaded. Cannot perform detection.")
            return [[] for _ in frames] # Return empty detections for all frames

        if not frames:
            return []

        print(f"Performing YOLO detection on {len(frames)} frame(s)...")
        try:
            # Process frames in batches if possible, or one by one
            # The YOLO model can take a list of frames directly
            results_list = self.model(frames, verbose=False) # verbose=False to reduce console output during inference
        except Exception as e:
            print(f"Error during YOLO model inference: {e}")
            return [[] for _ in frames]

        for results in results_list: # results is of type ultralytics.engine.results.Results
            frame_detections = []
            if results.boxes is not None and results.names is not None:
                for box in results.boxes:
                    class_id = int(box.cls.item()) # box.cls is a tensor, get scalar
                    class_name = results.names[class_id]
                    confidence = float(box.conf.item()) # box.conf is a tensor
                    # box.xyxy is a tensor of shape [1, 4], squeeze to get [4] then convert to list/tuple
                    bounding_box = tuple(map(int, box.xyxy.squeeze().tolist())) 
                    
                    detection_info = {
                        'class_id': class_id,
                        'class_name': class_name,
                        'bounding_box': bounding_box, # (x1, y1, x2, y2)
                        'confidence': confidence
                    }
                    frame_detections.append(detection_info)
            all_frames_detections.append(frame_detections)
        
        print(f"Detection complete. Found detections in {sum(1 for fd in all_frames_detections if fd)} out of {len(frames)} frames.")
        return all_frames_detections

if __name__ == '__main__':
    print("Running YOLODetector Example...")

    # This example assumes 'yolov8n.pt' can be downloaded or is already available.
    # It also assumes you might have a sample image.
    # For simplicity, we'll create a dummy frame.
    
    # 1. Initialize Detector
    print("\n--- Initializing YOLODetector ---")
    try:
        detector = YOLODetector(model_name='yolov8n.pt') # yolov8n.pt is small and good for testing
    except Exception as e:
        print(f"Failed to initialize YOLODetector: {e}")
        print("This might be due to network issues if the model needs to be downloaded,")
        print("or if the ultralytics library is not installed correctly.")
        detector = None # Ensure detector is None if initialization fails

    if detector and detector.model:
        # 2. Create Dummy Frames (or load real images)
        # Using a simple black frame. YOLOv8n might not detect anything specific in it,
        # or it might detect common objects if trained on them and they appear by chance.
        # For a more robust test, use an image known to have objects yolov8n can detect.
        print("\n--- Creating Dummy Frames ---")
        dummy_frame_1 = np.zeros((480, 640, 3), dtype=np.uint8) # Black frame
        
        # Create a frame with a colored square - yolov8n is unlikely to detect this as a specific object
        # unless it's by chance or resembles something in its training data.
        # A better test would use an image with, e.g., a person or a car.
        dummy_frame_2 = np.full((480, 640, 3), (200, 200, 200), dtype=np.uint8) # Light gray background
        cv2.rectangle(dummy_frame_2, (100, 100), (200, 200), (0, 255, 0), -1) # Green square
        
        frames_to_test = [dummy_frame_1, dummy_frame_2]
        print(f"Created {len(frames_to_test)} dummy frames for detection.")

        # 3. Perform Detection
        print("\n--- Performing Object Detection ---")
        detections = detector.detect_objects(frames_to_test)

        # 4. Print Results
        print("\n--- Detection Results ---")
        if detections:
            for i, frame_dets in enumerate(detections):
                print(f"Frame {i+1}: {len(frame_dets)} detections")
                for det in frame_dets:
                    print(f"  - Class: {det['class_name']} (ID: {det['class_id']}), "
                          f"Confidence: {det['confidence']:.4f}, BBox: {det['bounding_box']}")
        else:
            print("No detections returned or an error occurred.")
            
        # Example with a real image (if available)
        # To test with a real image, ensure the image path is correct.
        # For example, create a 'data' directory in your project root and place 'sample_image.jpg' there.
        sample_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'sample_image.jpg')
        # Create a dummy sample image for testing if it does not exist
        if not os.path.exists(sample_image_path):
            print(f"\nAttempting to create a dummy 'sample_image.jpg' in 'data/' as it's missing.")
            data_dir = os.path.dirname(sample_image_path)
            if not os.path.exists(data_dir):
                try:
                    os.makedirs(data_dir)
                except OSError as e:
                    print(f"Could not create data directory {data_dir}: {e}")

            if os.path.exists(data_dir):
                try:
                    # Create a simple image with some colored rectangles
                    # This is still not guaranteed to be detected reliably by yolov8n as specific objects
                    # but serves as a non-trivial image input.
                    import cv2 # Import here to avoid making it a hard dependency for the whole file if not used.
                    img_for_test = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.rectangle(img_for_test, (50, 50), (150, 150), (0, 0, 255), -1)  # Red square
                    cv2.rectangle(img_for_test, (200, 100), (350, 300), (0, 255, 0), -1) # Green rectangle
                    cv2.circle(img_for_test, (500, 250), 50, (255, 0, 0), -1) # Blue circle
                    cv2.imwrite(sample_image_path, img_for_test)
                    print(f"Created a dummy sample image at: {sample_image_path}")
                except Exception as e_img:
                    print(f"Could not create dummy sample image: {e_img}")


        if os.path.exists(sample_image_path):
            print(f"\n--- Testing with a sample image: {sample_image_path} ---")
            try:
                import cv2 # Make sure cv2 is available if testing with real images
                img = cv2.imread(sample_image_path)
                if img is not None:
                    real_image_detections = detector.detect_objects([img])
                    if real_image_detections:
                        for i, frame_dets in enumerate(real_image_detections):
                            print(f"Sample Image Detections: {len(frame_dets)} detections")
                            for det in frame_dets:
                                print(f"  - Class: {det['class_name']} (ID: {det['class_id']}), "
                                      f"Confidence: {det['confidence']:.4f}, BBox: {det['bounding_box']}")
                    else:
                        print("No detections found in the sample image, or an error occurred.")
                else:
                    print(f"Could not read the sample image at {sample_image_path}. Skipping this test.")
            except ImportError:
                print("OpenCV (cv2) is not installed. Cannot load sample image for testing. Skipping.")
            except Exception as e:
                print(f"An error occurred while processing sample image: {e}")
        else:
            print(f"\nSample image {sample_image_path} not found. Skipping real image test.")
            print("You can place an image (e.g., with people, cars) there for a better test.")

    else:
        print("YOLO Detector not initialized. Skipping detection tests.")

    print("\nYOLODetector Example finished.")
