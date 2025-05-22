import sys
import os

# Adjust Python path to include 'src' and project root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from sqlalchemy import create_engine
from src.database.database_setup import init_db, DATABASE_URL
from src.database.crud import get_db_session, add_video_configurations # To add test data
from src.database.models import VideoConfiguration # For type hinting and queries
from src.processing_core.scheduler import VideoScheduler

def main():
    print("Running Video Scheduler Test Script...")

    # Ensure the data directory exists (as init_db expects './data/')
    data_dir_path = os.path.join(parent_dir, "data")
    if not os.path.exists(data_dir_path):
        os.makedirs(data_dir_path)
        print(f"Created data directory: {data_dir_path}")

    # 1. Initialize Database
    try:
        print("Initializing database...")
        # init_db() expects to be run from a context where './data/' is valid (project root)
        # Since this script is in 'scripts/', and DATABASE_URL is 'sqlite:///./data/video_processing.db'
        # it should correctly point to 'project_root/data/video_processing.db'
        init_db()
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Ensure the 'data' directory exists at the project root.")
        sys.exit(1)

    # 2. Create Engine and Session
    try:
        # DATABASE_URL from database_setup is relative to project root where 'data' folder is
        engine = create_engine(DATABASE_URL)
        session = get_db_session(engine)
        print("Database session established.")
    except Exception as e:
        print(f"Error creating database engine or session: {e}")
        sys.exit(1)

    # 3. Add some sample pending videos (optional, for testing)
    # This helps ensure there's something to schedule.
    # These will be skipped if video_path already exists.
    print("\nAdding/Verifying sample video configurations for testing...")
    sample_configs = [
        {'video_path': '/test/scheduler_script_video1.mp4', 'video_name': 'Script Test Video 1 (Prio 1)', 'priority': 1, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/scheduler_script_video2.avi', 'video_name': 'Script Test Video 2 (Prio 2)', 'priority': 2, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/scheduler_script_video3.mkv', 'video_name': 'Script Test Video 3 (Prio 1, older)', 'priority': 1, 'enabled': True, 'processing_status': 'pending'},
    ]
    # To ensure FIFO for same priority, we can add them one by one and query to see creation order later if needed
    # For now, add_video_configurations handles adding them.
    add_video_configurations(session, sample_configs) # This function prints its own summary

    # 4. Instantiate VideoScheduler
    scheduler = VideoScheduler(db_session=session)
    print("\nVideoScheduler instantiated.")

    # 5. Fetch and process videos in a loop (e.g., process 2 videos)
    for i in range(2):
        print(f"\n--- Cycle {i+1} ---")
        next_video = scheduler.get_next_video_to_process()

        if next_video:
            print(f"Fetched video: ID {next_video.id}, Name: {next_video.video_name}, Path: {next_video.video_path}, Prio: {next_video.priority}, Status: {next_video.processing_status}")
            
            print(f"Simulating processing for video ID: {next_video.id}...")
            scheduler.mark_video_processing_started(next_video.id)
            
            # Simulate some work (e.g., a short delay or some dummy operation)
            print(f"Video ID {next_video.id} is now 'processing'.")
            
            # Simulate completion
            scheduler.mark_video_completed(next_video.id)
            print(f"Video ID {next_video.id} marked as 'completed'.")
        else:
            print("No more pending videos available to process in this cycle.")
            break # Exit loop if no more videos

    # 6. Verify final states (optional)
    print("\nQuerying final state of test videos processed by this script:")
    test_video_paths = [config['video_path'] for config in sample_configs]
    processed_videos_query = session.query(VideoConfiguration).filter(VideoConfiguration.video_path.in_(test_video_paths))
    
    # Print results of video configurations
    for video in processed_videos_query.all():
        print(f"  Video Config: ID {video.id}, Path: {video.video_path}, Status: {video.processing_status}, Updated: {video.updated_at}")
        # Query and print associated detection results for this video
        from src.database.models import DetectionResult # Import here for this specific query
        detections = session.query(DetectionResult).filter(DetectionResult.video_configuration_id == video.id).all()
        if detections:
            print(f"    Found {len(detections)} detection results for Video ID {video.id}:")
            for det_idx, det_res in enumerate(detections[:3]): # Print first 3 detections as sample
                print(f"      - Frame {det_res.frame_number}: Class '{det_res.class_name}', Conf: {det_res.confidence:.2f}, Box: ({det_res.x1},{det_res.y1},{det_res.x2},{det_res.y2})")
            if len(detections) > 3:
                print(f"      ... and {len(detections)-3} more detections not shown.")
        else:
            print(f"    No detection results found for Video ID {video.id}.")
            
    if not processed_videos_query.first(): # Check if any videos were found at all
        print("No videos found matching the test paths for final state verification.")

    # 7. Clean up session
    session.close()
    print("\nDatabase session closed.")
    print("Scheduler and Processing Test Script finished.")
    print(f"To run this script, use: python {os.path.join('scripts', os.path.basename(__file__))}")
    print("Ensure your database 'data/video_processing.db' is in the project root.")
    print("And that necessary models (e.g., yolov8n.pt) are downloadable or cached by ultralytics.")


def full_processing_simulation(db_session: Session, scheduler: VideoScheduler):
    """
    Simulates the full processing of one video from the queue.
    """
    print("\n--- Starting Full Processing Simulation ---")
    
    next_video_to_process = scheduler.get_next_video_to_process()

    if not next_video_to_process:
        print("Full Processing Sim: No video found by scheduler. Ending simulation.")
        return

    print(f"Full Processing Sim: Picked Video ID {next_video_to_process.id} (Path: {next_video_to_process.video_path}) for processing.")
    scheduler.mark_video_processing_started(next_video_to_process.id)

    # Initialize components for processing
    # FrameExtractor (dummy video path for now, as we don't have real videos in test setup)
    # The dummy video created by frame_extractor.py is in data/dummy_test_video.mp4
    # We need to ensure this path is valid or use a placeholder.
    # For this test, we'll use the dummy video path generated by frame_extractor's main.
    
    # Path to the dummy video (ensure it's created, e.g. by running frame_extractor.py once)
    # Or, create it here if it doesn't exist.
    dummy_video_file_for_processing = os.path.join(parent_dir, "data", "dummy_processing_video.mp4")
    if not os.path.exists(dummy_video_file_for_processing):
        print(f"Full Processing Sim: Dummy video {dummy_video_file_for_processing} not found, creating...")
        from src.processing_core.frame_extractor import extract_frames # To access its dummy video creation part
        # This is a bit of a hack. Ideally, test videos are managed better.
        # The __main__ of frame_extractor creates "data/dummy_test_video.mp4"
        # Let's try to use that logic, or simplify.
        import cv2
        width, height, fps, duration = 320, 240, 10, 2 # 2 seconds, 10 fps = 20 frames
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(dummy_video_file_for_processing, fourcc, fps, (width, height))
        if out.isOpened():
            for _ in range(int(fps*duration)):
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                out.write(frame)
            out.release()
            print(f"Full Processing Sim: Created dummy video {dummy_video_file_for_processing} for test.")
        else:
            print(f"Full Processing Sim: FAILED to create dummy video {dummy_video_file_for_processing}. Processing may fail.")
            scheduler.mark_video_failed(next_video_to_process.id) # Mark failed as cannot process
            return

    video_actual_path = dummy_video_file_for_processing # Use this dummy video for processing

    from src.processing_core.frame_extractor import extract_frames
    from src.processing_core.yolo_detector import YOLODetector
    from src.processing_core.advanced_detector import AdvancedDetector
    from src.processing_core.pipeline import process_video_frame

    try:
        print(f"Full Processing Sim: Extracting frames from {video_actual_path}...")
        # Extract 1 frame per second for quick test
        extracted_frames = extract_frames(video_actual_path, frames_per_second_target=1.0) 
        if not extracted_frames:
            print(f"Full Processing Sim: No frames extracted from {video_actual_path}. Marking as failed.")
            scheduler.mark_video_failed(next_video_to_process.id)
            return

        print(f"Full Processing Sim: Extracted {len(extracted_frames)} frames.")

        # Initialize Detectors (assuming yolov8n.pt can be downloaded/cached)
        yolo_detector = YOLODetector(model_name='yolov8n.pt')
        # Use default filter settings for AdvancedDetector for this test
        # (min_conf=0.5, no class filter, iou_merge=0.5, class_specific_nms=True)
        advanced_detector = AdvancedDetector(yolo_detector=yolo_detector) 
        
        print("Full Processing Sim: Processing frames...")
        for frame_idx, frame_data in enumerate(extracted_frames):
            process_video_frame(
                db_session=db_session,
                video_config=next_video_to_process,
                frame_number=frame_idx, # Use index as frame number
                frame=frame_data,
                advanced_detector=advanced_detector
                # No filter_config_override, use AdvancedDetector's defaults
            )
        
        scheduler.mark_video_completed(next_video_to_process.id)
        print(f"Full Processing Sim: Video ID {next_video_to_process.id} marked as 'completed'.")

    except Exception as e:
        print(f"Full Processing Sim: An error occurred during processing of video ID {next_video_to_process.id}: {e}")
        scheduler.mark_video_failed(next_video_to_process.id)
        # Print traceback for more details on the error
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Original main() content is now part of the simulation setup
    print("Running Video Scheduler and Processing Test Script...")

    data_dir_path = os.path.join(parent_dir, "data")
    if not os.path.exists(data_dir_path):
        os.makedirs(data_dir_path)
        print(f"Created data directory: {data_dir_path}")

    try:
        print("Initializing database...")
        init_db()
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

    try:
        engine = create_engine(DATABASE_URL)
        session = get_db_session(engine)
        print("Database session established.")
    except Exception as e:
        print(f"Error creating database engine or session: {e}")
        sys.exit(1)

    print("\nAdding/Verifying sample video configurations for testing...")
    # Add some variety in priority and paths for scheduler testing
    sample_configs = [
        {'video_path': '/test/sim_video_high_prio.mp4', 'video_name': 'Sim Test High Prio', 'priority': 1, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/sim_video_mid_prio.avi', 'video_name': 'Sim Test Mid Prio', 'priority': 2, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/sim_video_low_prio.mkv', 'video_name': 'Sim Test Low Prio', 'priority': 3, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/sim_video_disabled.mp4', 'video_name': 'Sim Test Disabled', 'priority': 1, 'enabled': False, 'processing_status': 'pending'},
    ]
    add_video_configurations(session, sample_configs)

    scheduler_instance = VideoScheduler(db_session=session)
    print("\nVideoScheduler instantiated.")
    
    # Run the full processing simulation for a couple of videos (if available)
    full_processing_simulation(db_session=session, scheduler=scheduler_instance)
    full_processing_simulation(db_session=session, scheduler=scheduler_instance) # Try to process a second one

    # Query and display results (as in the original main)
    print("\n--- Final State Verification (After Simulation) ---")
    # Query all video configurations to see their final states
    all_video_configs = session.query(VideoConfiguration).all()
    if all_video_configs:
        for video_conf in all_video_configs:
            print(f"  Video Config: ID {video_conf.id}, Name: '{video_conf.video_name}', Path: {video_conf.video_path}, Prio: {video_conf.priority}, Enabled: {video_conf.enabled}, Status: {video_conf.processing_status}, Created: {video_conf.created_at}, Updated: {video_conf.updated_at}")
            # Query and print associated detection results for this video
            from src.database.models import DetectionResult # Import here for this specific query
            detections = session.query(DetectionResult).filter(DetectionResult.video_configuration_id == video_conf.id).order_by(DetectionResult.frame_number).all()
            if detections:
                print(f"    Found {len(detections)} detection results for Video ID {video_conf.id}:")
                for det_idx, det_res in enumerate(detections[:3]): # Print first 3 detections as sample
                    print(f"      - Frame {det_res.frame_number}: Class '{det_res.class_name}', Conf: {det_res.confidence:.2f}, Box: ({det_res.x1},{det_res.y1},{det_res.x2},{det_res.y2}), Timestamp: {det_res.timestamp}")
                if len(detections) > 3:
                    print(f"      ... and {len(detections)-3} more detections not shown.")
            else:
                print(f"    No detection results found for Video ID {video_conf.id}.")
    else:
        print("No video configurations found in the database for final state verification.")

    session.close()
    print("\nDatabase session closed.")
    print("Scheduler and Processing Test Script finished.")
    print(f"To run this script, use: python {os.path.join('scripts', os.path.basename(__file__))}")
    print("Ensure your database 'data/video_processing.db' is in the project root.")
    print("And that necessary models (e.g., yolov8n.pt) are downloadable or cached by ultralytics.")
