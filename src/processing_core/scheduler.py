import sys
import os

# Adjust path to import from parent directory (src)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy.orm import Session
from database.models import VideoConfiguration
from database.crud import get_pending_videos, update_video_status

class VideoScheduler:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_next_video_to_process(self) -> VideoConfiguration | None:
        """
        Fetches the highest priority pending video.
        Updates its status to 'dequeued' to prevent other schedulers from picking it up.
        """
        pending_videos = get_pending_videos(self.db_session, limit=1)
        if pending_videos:
            video_to_process = pending_videos[0]
            # Update status to 'dequeued' to prevent other instances from picking it up.
            # This is an important step in a distributed or multi-worker environment.
            updated_video = update_video_status(self.db_session, video_to_process.id, 'dequeued')
            if updated_video:
                print(f"Video ID {updated_video.id} dequeued for processing.")
                return updated_video
            else:
                # This case should ideally not happen if get_pending_videos returned a video
                print(f"Error: Failed to update status for video ID {video_to_process.id} after fetching.")
                return None
        else:
            print("No pending videos available to process.")
            return None

    def mark_video_processing_started(self, video_id: int):
        """
        Marks a video as 'processing'.
        """
        print(f"Scheduler: Marking video ID {video_id} as 'processing'.")
        return update_video_status(self.db_session, video_id, 'processing')

    def mark_video_completed(self, video_id: int):
        """
        Marks a video as 'completed'.
        """
        print(f"Scheduler: Marking video ID {video_id} as 'completed'.")
        return update_video_status(self.db_session, video_id, 'completed')

    def mark_video_failed(self, video_id: int):
        """
        Marks a video as 'failed'.
        """
        print(f"Scheduler: Marking video ID {video_id} as 'failed'.")
        return update_video_status(self.db_session, video_id, 'failed')

if __name__ == '__main__':
    # This is an example of how to use the VideoScheduler
    # It requires the database to be set up and potentially have some data.
    
    # Setup (run from project root for correct imports and DB path)
    # Ensure you are in the project root directory for this example to work correctly
    # e.g., by running: python src/processing_core/scheduler.py
    
    # Since this script is in src/processing_core, and DATABASE_URL in database_setup
    # is "sqlite:///./data/video_processing.db", we need to adjust path for db setup for this test
    # Or ensure that 'data' directory exists at the project root.
    
    print("Running VideoScheduler example...")
    
    # Path adjustments for direct execution
    project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
    sys.path.append(project_root) # Add project root to sys.path
    
    from sqlalchemy import create_engine
    from database.database_setup import init_db, DATABASE_URL
    from database.crud import get_db_session, add_video_configurations # For adding test data

    # 1. Initialize DB (make sure 'data' folder exists at project root or adjust DATABASE_URL)
    # If data directory doesn't exist in the expected location (project_root/data), create it
    data_dir_for_test = os.path.join(project_root, "data")
    if not os.path.exists(data_dir_for_test):
        os.makedirs(data_dir_for_test)
        print(f"Created directory: {data_dir_for_test} for the test database.")

    actual_db_url = DATABASE_URL.replace("///./", f"///{project_root}/") # Make sure path is absolute or relative to root
    print(f"Using Database URL: {actual_db_url}")
    
    try:
        init_db() # This will use the DATABASE_URL defined in database_setup.py
                  # which expects to be run from a context where './data/' is valid.
                  # For this test, we assume it creates 'data/video_processing.db' relative to project root.
    except Exception as e:
        print(f"Error during init_db: {e}. This might be due to relative path issues.")
        print("Ensure you run this test from the project root or adjust DATABASE_URL in database_setup.py")
        sys.exit(1)

    engine = create_engine(actual_db_url) # Use the adjusted URL for the engine
    session = get_db_session(engine)

    # 2. Add some sample pending videos if none exist (optional, for testing)
    print("\nAdding sample video configurations for testing...")
    sample_configs = [
        {'video_path': '/test/video_scheduler1.mp4', 'video_name': 'Scheduler Test Video 1 (Prio 1)', 'priority': 1, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/video_scheduler2.avi', 'video_name': 'Scheduler Test Video 2 (Prio 2)', 'priority': 2, 'enabled': True, 'processing_status': 'pending'},
        {'video_path': '/test/video_disabled.mkv', 'video_name': 'Scheduler Test Disabled', 'priority': 1, 'enabled': False, 'processing_status': 'pending'},
        {'video_path': '/test/video_processed.mp4', 'video_name': 'Scheduler Test Processed', 'priority': 3, 'enabled': True, 'processing_status': 'completed'},
    ]
    add_video_configurations(session, sample_configs) # This function prints its own summary

    # 3. Instantiate VideoScheduler
    scheduler = VideoScheduler(db_session=session)
    print("\nVideoScheduler instantiated.")

    # 4. Get next video
    print("\nAttempting to get next video to process...")
    next_video = scheduler.get_next_video_to_process()

    if next_video:
        print(f"\nFetched video: ID {next_video.id}, Name: {next_video.video_name}, Path: {next_video.video_path}, Prio: {next_video.priority}, Status: {next_video.processing_status}")

        # 5. Simulate processing lifecycle
        print(f"\nSimulating processing for video ID: {next_video.id}")
        scheduler.mark_video_processing_started(next_video.id)
        
        # Simulate some work...
        print("Video processing...")
        
        scheduler.mark_video_completed(next_video.id)
        
        # Try fetching another video
        print("\nAttempting to get another video to process...")
        another_video = scheduler.get_next_video_to_process()
        if another_video:
            print(f"\nFetched another video: ID {another_video.id}, Name: {another_video.video_name}, Status: {another_video.processing_status}")
            print(f"Simulating failure for video ID: {another_video.id}")
            scheduler.mark_video_failed(another_video.id)
        else:
            print("No more videos to process after the first one.")
            
    else:
        print("\nNo video fetched by the scheduler (this might be expected if all are processed/disabled or DB is empty).")

    # 6. Query to see final states (optional)
    print("\nFinal state of sample videos:")
    all_videos_after_test = session.query(VideoConfiguration).filter(VideoConfiguration.video_path.like('%/test/video_scheduler%')).all()
    for v in all_videos_after_test:
        print(f"  ID: {v.id}, Path: {v.video_path}, Status: {v.processing_status}, Updated: {v.updated_at}")

    session.close()
    print("\nVideoScheduler example finished.")
    print("Note: If you run this multiple times, 'add_video_configurations' will skip existing paths.")
    print("Consider clearing the database (data/video_processing.db) or adding unique paths for fresh tests.")
