import numpy as np
import sys
import os

# Adjust path to import from parent directory (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy.orm import Session
from database.models import VideoConfiguration # For type hinting
from database import crud # For add_detection_results
from processing_core.advanced_detector import AdvancedDetector # For type hinting

def process_video_frame(
    db_session: Session, 
    video_config: VideoConfiguration, 
    frame_number: int, 
    frame: np.ndarray, 
    advanced_detector: AdvancedDetector,
    filter_config_override: dict | None = None # Allow passing filter overrides
    ):
    """
    Processes a single video frame, performs detection, and saves results to the database.

    Args:
        db_session (Session): The SQLAlchemy database session.
        video_config (VideoConfiguration): The video configuration object from the database.
        frame_number (int): The index/number of the current frame.
        frame (np.ndarray): The video frame (as a NumPy array).
        advanced_detector (AdvancedDetector): The AdvancedDetector instance for object detection.
        filter_config_override (dict | None): Optional dictionary to override the AdvancedDetector's
                                              default filter configurations for this specific frame/call.
    """
    if not isinstance(video_config, VideoConfiguration) or video_config.id is None:
        print("Error (process_video_frame): Invalid video_config object or ID is missing.")
        return

    if not isinstance(frame, np.ndarray):
        print(f"Error (process_video_frame): Frame {frame_number} for video {video_config.id} is not a NumPy array.")
        return

    print(f"\nProcessing frame {frame_number} for video ID: {video_config.id} (Path: {video_config.video_path})")

    # 1. Perform detection using AdvancedDetector
    # The detect_with_localization method now handles merging and filtering internally.
    # It uses filter settings from AdvancedDetector's init, unless overridden.
    try:
        final_detections = advanced_detector.detect_with_localization(
            frame, 
            filter_config_override=filter_config_override
        )
        print(f"Frame {frame_number}: Found {len(final_detections)} final detections after processing.")
    except Exception as e:
        print(f"Error during detection for frame {frame_number}, video ID {video_config.id}: {e}")
        # Depending on desired robustness, might want to continue to next frame or stop.
        # For now, just print error and don't save results for this frame.
        return 

    # 2. Decision to Save: Save if filtered_detections is not empty.
    if final_detections:
        print(f"Frame {frame_number}: {len(final_detections)} detections to save for video ID {video_config.id}.")
        try:
            crud.add_detection_results(
                session=db_session,
                video_config_id=video_config.id,
                frame_number=frame_number,
                detections=final_detections
            )
            # crud.add_detection_results already prints a success message.
        except Exception as e:
            # crud.add_detection_results prints its own error, but we might want to log here too
            print(f"Error saving detection results for frame {frame_number}, video ID {video_config.id} to database: {e}")
            # Potentially mark the frame as failed for saving or retry later.
    else:
        print(f"Frame {frame_number}: No detections to save for video ID {video_config.id}.")

if __name__ == '__main__':
    print("Running Pipeline Example (Illustrative - Requires more setup for a real run)...")
    
    # This example is illustrative. A real run would require:
    # 1. Database setup and a valid session.
    # 2. A VideoConfiguration object from the database.
    # 3. A real frame (np.ndarray).
    # 4. An initialized YOLODetector and AdvancedDetector.

    # --- Mocking necessary components for demonstration ---
    from unittest.mock import MagicMock
    
    # Mock DB Session
    mock_db_session = MagicMock(spec=Session)

    # Mock VideoConfiguration object
    mock_video_config = VideoConfiguration(id=1, video_path="/test/video.mp4", video_name="Test Video")
    mock_video_config.id = 1 # Ensure ID is set if constructor doesn't handle it.

    # Mock Frame (e.g., a black frame)
    dummy_frame_for_pipeline = np.zeros((480, 640, 3), dtype=np.uint8)
    current_frame_number = 0

    # Mock YOLODetector (very basic)
    mock_yolo = MagicMock(spec=YOLODetector)
    def mock_yolo_detect(frames, verbose=False): # Match signature
        # Simulate finding one 'person'
        return [[{'class_id': 0, 'class_name': 'person', 'bounding_box': (10,10,60,110), 'confidence': 0.9}]] 
    mock_yolo.detect_objects = mock_yolo_detect
    
    # Mock AdvancedDetector
    # It will use the mock_yolo.
    # We use default filter settings for AdvancedDetector here.
    try:
        advanced_detector_instance = AdvancedDetector(yolo_detector=mock_yolo)
    except ValueError as ve:
        print(f"Failed to init AdvancedDetector with mock: {ve}")
        advanced_detector_instance = None
    except Exception as e: # Catch any other init errors from Yolo/AdvancedDetector
        print(f"An unexpected error occurred during AdvancedDetector init with mock: {e}")
        advanced_detector_instance = None


    if advanced_detector_instance:
        print("\n--- Simulating process_video_frame call ---")
        
        # Patch crud.add_detection_results to avoid actual DB interaction for this example
        with patch('database.crud.add_detection_results') as mock_add_detections_db:
            mock_add_detections_db.return_value = None # Simulate successful save
            
            process_video_frame(
                db_session=mock_db_session,
                video_config=mock_video_config,
                frame_number=current_frame_number,
                frame=dummy_frame_for_pipeline,
                advanced_detector=advanced_detector_instance
            )

            # Check if add_detection_results was called (if detections were found by mock)
            if mock_add_detections_db.called:
                print("\ncrud.add_detection_results was called (mocked).")
                call_args = mock_add_detections_db.call_args[1] # Get kwargs
                print(f"  Video Config ID: {call_args['video_config_id']}")
                print(f"  Frame Number: {call_args['frame_number']}")
                print(f"  Detections: {call_args['detections']}")
            else:
                # This would happen if the mock yolo/advanced detector returned no detections
                # or if the default filters in AdvancedDetector removed everything.
                # Our mock yolo always returns one person, and default AD filter is min_conf 0.5, no class filter.
                # So, it should be called.
                print("\ncrud.add_detection_results was NOT called. Check mock detection logic and AD filter defaults.")
    else:
        print("AdvancedDetector instance could not be created. Skipping simulation.")

    print("\nPipeline Example finished.")
