from sqlalchemy import create_engine
from .models import Base # Assuming models.py is in the same directory
import os

DATABASE_URL = "sqlite:///./data/video_processing.db"

def init_db():
    # Ensure the data directory exists
    data_dir = os.path.dirname(DATABASE_URL.split("///")[-1])
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created directory: {data_dir}")

    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}) # check_same_thread for SQLite
    
    # Create all tables in the engine. This is equivalent to "Create Table"
    # statements in raw SQL.
    Base.metadata.create_all(bind=engine)
    print("Database initialized and tables created (if they didn't exist).")

if __name__ == "__main__":
    init_db()
