from sqlalchemy.orm import Session
from .models import VideoConfiguration # Assuming models.py is in the same directory
from sqlalchemy.exc import IntegrityError

def get_db_session(engine):
    """Creates a new database session."""
    SessionLocal = Session(bind=engine)
    return SessionLocal()

def add_video_configurations(session: Session, configs: list[dict]):
    """
    Adds video configurations to the database.
    It checks for existing video_path and skips if already present.
    More sophisticated upsert logic can be added later.
    """
    added_count = 0
    skipped_count = 0
    
    for config_data in configs:
        # Check if a configuration with the same video_path already exists
        exists = session.query(VideoConfiguration).filter(VideoConfiguration.video_path == config_data['video_path']).first()
        
        if exists:
            print(f"Skipping: Video configuration for '{config_data['video_path']}' already exists.")
            skipped_count += 1
            continue
            
        # Create a new VideoConfiguration object
        # Ensure all required fields are present, providing defaults if necessary
        db_config = VideoConfiguration(
            video_path=config_data['video_path'],
            video_name=config_data.get('video_name'), 
            priority=config_data.get('priority', 3),
            enabled=config_data.get('enabled', True),
            processing_status=config_data.get('processing_status', 'pending')
            # created_at and updated_at have defaults in the model
        )
        
        try:
            session.add(db_config)
            session.commit()
            added_count += 1
            print(f"Added: Video configuration for '{db_config.video_path}'")
        except IntegrityError as e:
            session.rollback()
            # This might happen if a unique constraint (other than video_path if we add more) is violated
            print(f"Error adding video configuration for '{config_data['video_path']}': {e}. Skipped.")
            skipped_count += 1
        except Exception as e:
            session.rollback()
            print(f"An unexpected error occurred while adding '{config_data['video_path']}': {e}. Skipped.")
            skipped_count += 1
            
    print(f"\nSummary: Added {added_count} new configurations. Skipped {skipped_count} existing or erroneous configurations.")

if __name__ == '__main__':
    # Example Usage (requires database_setup.py and models.py to be working)
    from sqlalchemy import create_engine
    from .database_setup import init_db, DATABASE_URL 
    
    # 1. Initialize DB and create tables (if not already done)
    # init_db() # Usually called from the main script

    # 2. Create an engine and a session
    engine = create_engine(DATABASE_URL)
    session = get_db_session(engine)

    # 3. Example configurations (normally from Excel reader)
    example_configs = [
        {'video_path': '/test/videoA.mp4', 'video_name': 'Test Video A', 'priority': 1, 'enabled': True},
        {'video_path': '/test/videoB.avi', 'video_name': 'Test Video B', 'priority': 2, 'enabled': False},
        {'video_path': '/test/videoC.mkv', 'video_name': 'Test Video C'}, # Uses default priority and enabled
        {'video_path': '/test/videoA.mp4', 'video_name': 'Test Video A Duplicate', 'priority': 5} # Duplicate path
    ]

    print("Attempting to add example configurations...")
    add_video_configurations(session, example_configs)

    # 4. Verify (optional - query and print)
    print("\nCurrent configurations in database:")
    all_videos = session.query(VideoConfiguration).all()
    if all_videos:
        for video in all_videos:
            print(f"- ID: {video.id}, Path: {video.video_path}, Name: {video.video_name}, Prio: {video.priority}, Enabled: {video.enabled}, Status: {video.processing_status}")
    else:
        print("No configurations found in the database.")

    # 5. Clean up session
    session.close()
    print("\nExample finished. Note: This example directly manipulates the DB; run main script for full flow.")

def get_pending_videos(session: Session, limit: int = 10) -> list[VideoConfiguration]:
    """
    Fetches pending videos from the database, ordered by priority and creation date.
    """
    return session.query(VideoConfiguration)\
        .filter(VideoConfiguration.enabled == True, VideoConfiguration.processing_status == 'pending')\
        .order_by(VideoConfiguration.priority.asc(), VideoConfiguration.created_at.asc())\
        .limit(limit)\
        .all()

def update_video_status(session: Session, video_id: int, new_status: str) -> VideoConfiguration | None:
    """
    Updates the processing_status and updated_at timestamp of a video.
    """
    video = session.query(VideoConfiguration).filter(VideoConfiguration.id == video_id).first()
    if video:
        video.processing_status = new_status
        # video.updated_at = datetime.datetime.utcnow() # sqlalchemy will update this automatically due to onupdate
        session.commit()
        print(f"Video ID {video_id} status updated to '{new_status}'.")
        return video
    else:
        print(f"Error: Video ID {video_id} not found. Cannot update status.")
        return None

def add_detection_results(session: Session, video_config_id: int, frame_number: int, detections: list[dict]):
    """
    Adds detection results for a specific frame of a video to the database.

    Args:
        session (Session): The SQLAlchemy session.
        video_config_id (int): The ID of the VideoConfiguration entry.
        frame_number (int): The frame number for these detections.
        detections (list[dict]): A list of detection dictionaries. Each dict should have:
                                 'class_id', 'class_name', 'confidence', 
                                 and 'bounding_box' (tuple: x1, y1, x2, y2).
    """
    added_count = 0
    try:
        for det_data in detections:
            # Ensure bounding_box is present and has 4 elements
            bbox = det_data.get('bounding_box')
            if not bbox or len(bbox) != 4:
                print(f"Warning (add_detection_results): Skipping detection due to missing or invalid bounding_box: {det_data}")
                continue

            db_detection = DetectionResult(
                video_configuration_id=video_config_id,
                frame_number=frame_number,
                class_id=det_data.get('class_id'),
                class_name=det_data.get('class_name'),
                confidence=det_data.get('confidence'),
                x1=bbox[0],
                y1=bbox[1],
                x2=bbox[2],
                y2=bbox[3]
                # timestamp is defaulted by the model
            )
            session.add(db_detection)
            added_count += 1
        
        session.commit()
        if added_count > 0:
            print(f"Added {added_count} detection results for video_config_id={video_config_id}, frame={frame_number}.")
    except Exception as e:
        session.rollback()
        print(f"Error adding detection results for video_config_id={video_config_id}, frame={frame_number}: {e}")
        # Potentially re-raise or handle more gracefully depending on overall error strategy
        raise # Re-raise to signal failure to the caller for now


def get_detections_for_video(session: Session, video_config_id: int, frame_number: int = None) -> list[DetectionResult]:
    """
    Fetches all detection results for a given video_config_id.
    If frame_number is provided, it filters detections for that specific frame.
    Returns a list of DetectionResult objects.
    """
    query = session.query(DetectionResult).filter(DetectionResult.video_configuration_id == video_config_id)
    if frame_number is not None:
        query = query.filter(DetectionResult.frame_number == frame_number)
    
    results = query.order_by(DetectionResult.frame_number, DetectionResult.id).all()
    if results:
        print(f"Found {len(results)} detections for video_id={video_config_id}"
              f"{f', frame={frame_number}' if frame_number is not None else ''}.")
    else:
        print(f"No detections found for video_id={video_config_id}"
              f"{f', frame={frame_number}' if frame_number is not None else ''}.")
    return results


def get_detections_by_class(session: Session, class_name: str, video_config_id: int = None) -> list[DetectionResult]:
    """
    Fetches all detections matching a specific class_name.
    If video_config_id is provided, it scopes the search to that video.
    Returns a list of DetectionResult objects.
    """
    if not class_name:
        print("Warning (get_detections_by_class): class_name cannot be empty. Returning empty list.")
        return []
        
    query = session.query(DetectionResult).filter(DetectionResult.class_name == class_name)
    if video_config_id is not None:
        query = query.filter(DetectionResult.video_configuration_id == video_config_id)
        
    results = query.order_by(DetectionResult.video_configuration_id, DetectionResult.frame_number, DetectionResult.id).all()

    if results:
        print(f"Found {len(results)} detections for class_name='{class_name}'"
              f"{f', video_id={video_config_id}' if video_config_id is not None else ''}.")
    else:
        print(f"No detections found for class_name='{class_name}'"
              f"{f', video_id={video_config_id}' if video_config_id is not None else ''}.")
    return results
