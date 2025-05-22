import argparse
import os
import sys
import cv2 # For saving the image, and potentially re-extracting frame
import numpy as np

# Adjust Python path to include 'src' and project root
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from sqlalchemy import create_engine
from src.database.database_setup import init_db, DATABASE_URL
from src.database.crud import get_db_session, get_detections_for_video, get_video_configuration_by_id
from src.database.models import VideoConfiguration, DetectionResult # For type hinting
from src.utils.image_utils import draw_detections_on_frame
from src.processing_core.frame_extractor import extract_frames # To re-extract a specific frame

OUTPUT_VISUALIZATIONS_DIR = os.path.join(parent_dir, "data", "output_visualizations")

def main():
    parser = argparse.ArgumentParser(description="Query detection results for a video and visualize them on a frame.")
    parser.add_argument("video_config_id", type=int, help="ID of the VideoConfiguration to query.")
    parser.add_argument("--frame_number", type=int, default=None, help="Optional: Specific frame number to visualize. If not provided, only prints detection data.")
    
    args = parser.parse_args()

    if not os.path.exists(OUTPUT_VISUALIZATIONS_DIR):
        print(f"Creating output directory: {OUTPUT_VISUALIZATIONS_DIR}")
        os.makedirs(OUTPUT_VISUALIZATIONS_DIR)

    # 1. Initialize DB and Session
    try:
        engine = create_engine(DATABASE_URL)
        # init_db(engine) # Not strictly needed if DB is already initialized, but safe.
        session = get_db_session(engine)
        print("Database session established.")
    except Exception as e:
        print(f"Error creating database engine or session: {e}")
        sys.exit(1)

    # 2. Fetch Video Configuration (to get video path if needed for frame extraction)
    video_config = get_video_configuration_by_id(session, args.video_config_id)
    if not video_config:
        print(f"Error: VideoConfiguration with ID {args.video_config_id} not found.")
        session.close()
        sys.exit(1)
    
    print(f"\nQuerying detections for Video ID: {video_config.id} (Name: {video_config.video_name}, Path: {video_config.video_path})")

    # 3. Fetch Detections
    # If a specific frame_number is given for visualization, we only need detections for that frame.
    # Otherwise, fetch all detections for the video to print them.
    target_frame_for_query = args.frame_number if args.frame_number is not None else None
    detections_from_db = get_detections_for_video(session, args.video_config_id, frame_number=target_frame_for_query)

    if not detections_from_db:
        print(f"No detections found for Video ID {args.video_config_id}" + (f", Frame {args.frame_number}" if args.frame_number is not None else "") + ".")
        session.close()
        return

    # 4. Print Detections to Console
    print("\n--- Detection Results ---")
    for det_res in detections_from_db:
        print(f"  Frame {det_res.frame_number}: ID {det_res.id}, Class '{det_res.class_name}' (ID: {det_res.class_id}), "
              f"Conf: {det_res.confidence:.2f}, Box: ({det_res.x1},{det_res.y1},{det_res.x2},{det_res.y2}), "
              f"Timestamp: {det_res.timestamp}")

    # 5. Visualize on Frame (if frame_number is specified)
    if args.frame_number is not None:
        print(f"\nAttempting to visualize detections on Frame {args.frame_number}...")
        
        # Filter the already fetched detections if they were for all frames, or use them if already specific
        # (Our current get_detections_for_video already handles this, so detections_from_db is correct)
        detections_for_specific_frame = detections_from_db # They are already filtered if frame_number was given to query
        
        if not detections_for_specific_frame:
             print(f"No detections found specifically for Frame {args.frame_number} to visualize (even if other frames had detections).")
             session.close()
             return

        # Attempt to re-extract the frame
        # This assumes the video_config.video_path is accessible and valid.
        # And that frame_extractor can get a specific frame.
        # extract_frames gets frames based on FPS target. We need a way to get a specific frame by index.
        # Let's modify this part: extract_frames as is extracts multiple frames.
        # We need a more targeted frame extraction for visualization.
        
        # Simplified approach: extract_frames with a very high target FPS around the specific frame.
        # This is inefficient. A better way would be a dedicated function: get_frame_by_number(video_path, frame_num)
        
        # For now, let's try to load the dummy video created by run_scheduler_test.py or frame_extractor.py,
        # assuming frame_number corresponds to an index in its extracted frames.
        # This is a placeholder for a more robust frame loading mechanism.
        
        # Let's use the video_path from the video_config
        video_file_path = video_config.video_path
        if not os.path.exists(video_file_path):
            # As a fallback for testing, try the dummy video path if the configured one doesn't exist
            print(f"Warning: Video path {video_file_path} from DB not found.")
            # This path is consistent with what run_scheduler_test.py creates for simulation
            fallback_dummy_path = os.path.join(parent_dir, "data", "dummy_processing_video.mp4")
            if os.path.exists(fallback_dummy_path):
                print(f"Attempting to use fallback dummy video: {fallback_dummy_path}")
                video_file_path = fallback_dummy_path
            else:
                print(f"Error: Video file {video_file_path} (and fallback dummy) not found. Cannot extract frame for visualization.")
                session.close()
                return

        # Attempt to extract the specific frame
        # This is still not ideal as extract_frames gets multiple frames.
        # A proper solution needs cv2.VideoCapture to seek to the frame.
        print(f"Attempting to extract frame {args.frame_number} from {video_file_path}...")
        cap = cv2.VideoCapture(video_file_path)
        original_frame = None
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_file_path} to extract frame.")
        else:
            # Set the frame position (0-based index)
            cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame_number)
            ret, frame_data = cap.read()
            if ret:
                original_frame = frame_data
                print(f"Successfully extracted Frame {args.frame_number} (shape: {original_frame.shape}).")
            else:
                print(f"Error: Could not read Frame {args.frame_number} from video {video_file_path}.")
            cap.release()

        if original_frame is not None:
            # Detections for draw_detections_on_frame need 'bounding_box', 'class_name', 'confidence'
            # Our DetectionResult model has these (x1,y1,x2,y2 are separate)
            detections_to_draw = []
            for db_det in detections_for_specific_frame:
                detections_to_draw.append({
                    'class_name': db_det.class_name,
                    'confidence': db_det.confidence,
                    'bounding_box': (db_det.x1, db_det.y1, db_det.x2, db_det.y2)
                })

            annotated_frame = draw_detections_on_frame(original_frame, detections_to_draw)
            
            output_filename = f"annotated_video{args.video_config_id}_frame{args.frame_number}.jpg"
            output_filepath = os.path.join(OUTPUT_VISUALIZATIONS_DIR, output_filename)
            
            try:
                cv2.imwrite(output_filepath, annotated_frame)
                print(f"Annotated frame saved to: {output_filepath}")
            except Exception as e:
                print(f"Error saving annotated frame to {output_filepath}: {e}")
        else:
            print(f"Could not load Frame {args.frame_number} for visualization.")

    session.close()
    print("\nQuery and Visualize script finished.")

if __name__ == "__main__":
    # Example usage:
    # Assuming you have run the scheduler test and it processed video ID 1, with detections on frame 0 and 1.
    # python scripts/query_and_visualize_detections.py 1 --frame_number 0
    # python scripts/query_and_visualize_detections.py 1 --frame_number 1
    # python scripts/query_and_visualize_detections.py 1 (prints all detections for video 1)
    
    # Before running, ensure database exists and has data.
    # The dummy video "data/dummy_processing_video.mp4" should also exist if you expect frame extraction to work.
    # This dummy video is created by `run_scheduler_test.py` if it doesn't exist.
    
    main()
