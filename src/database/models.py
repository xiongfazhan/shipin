from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class VideoConfiguration(Base):
    __tablename__ = "video_configurations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_path = Column(String, nullable=False, unique=True) # Assuming video_path should be unique
    video_name = Column(String)
    priority = Column(Integer, default=3)
    enabled = Column(Boolean, default=True)
    processing_status = Column(String, default='pending')
    # New nullable columns for video stream configuration parameters
    risk_level = Column(String, nullable=True)
    frame_extraction_interval = Column(Float, nullable=True)
    max_frames_to_process = Column(Integer, nullable=True)
    yolo_model_name = Column(String, nullable=True)
    detection_confidence_threshold = Column(Float, nullable=True)
    result_destination_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<VideoConfiguration(id={self.id}, video_name='{self.video_name}', status='{self.processing_status}')>"

if __name__ == '__main__':
    # Example of creating an engine and creating tables (for testing purposes)
    # This part will be in database_setup.py ideally
    # engine = create_engine('sqlite:///./data/video_processing.db') # Example, use your actual DB URL
    # Base.metadata.create_all(bind=engine)
    # print("Database tables created (if they didn't exist).")


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    video_configuration_id = Column(Integer, sqlalchemy.ForeignKey("video_configurations.id"), nullable=False)
    frame_number = Column(Integer, nullable=False) # Index of the frame
    class_id = Column(Integer)
    class_name = Column(String)
    confidence = Column(sqlalchemy.Float) # Ensure sqlalchemy.Float is used for broader compatibility
    x1 = Column(Integer)
    y1 = Column(Integer)
    x2 = Column(Integer)
    y2 = Column(Integer)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    video_config = sqlalchemy.orm.relationship("VideoConfiguration") # Optional: for easier access

    def __repr__(self):
        return (f"<DetectionResult(id={self.id}, video_id={self.video_configuration_id}, frame={self.frame_number}, "
                f"class='{self.class_name}', conf={self.confidence:.2f}, box=({self.x1},{self.y1},{self.x2},{self.y2}))>")

if __name__ == '__main__':
    # Updated example for testing model definitions
    from sqlalchemy import create_engine # Ensure create_engine is imported
    import sqlalchemy # for ForeignKey, Float, orm.relationship

    engine = create_engine('sqlite:///./data/video_processing_test_models.db') # Use a test DB
    Base.metadata.create_all(bind=engine)
    print("Database tables (including detection_results) created in video_processing_test_models.db (if they didn't exist).")
