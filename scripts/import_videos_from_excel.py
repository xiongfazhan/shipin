import argparse
import os
import sys

# Adjust the Python path to include the 'src' directory
# This is a common way to make modules in 'src' importable when running scripts from 'scripts'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from src.database.database_setup import init_db, DATABASE_URL
from src.excel_importer.importer import read_excel_config
from src.database.crud import add_video_configurations, get_db_session
from sqlalchemy import create_engine

def main():
    parser = argparse.ArgumentParser(description="Import video configurations from an Excel file into the database.")
    parser.add_argument("excel_file", help="Path to the Excel file containing video configurations.")
    
    args = parser.parse_args()
    excel_file_path = args.excel_file

    print("Starting video import process...")

    # 1. Initialize Database
    try:
        print("Initializing database...")
        init_db() # This creates the data directory and video_processing.db if they don't exist
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

    # 2. Read Excel Configuration
    print(f"Reading configurations from Excel file: {excel_file_path}...")
    video_configs = read_excel_config(excel_file_path)
    
    if not video_configs:
        print("No video configurations found in the Excel file or an error occurred during reading.")
        sys.exit(0) # Exit gracefully if no configs or error already printed by reader

    # 3. Establish Database Session
    try:
        engine = create_engine(DATABASE_URL)
        session = get_db_session(engine)
        print("Database session established.")
    except Exception as e:
        print(f"Error establishing database session: {e}")
        sys.exit(1)

    # 4. Add Configurations to Database
    print("Adding video configurations to the database...")
    try:
        add_video_configurations(session, video_configs)
    except Exception as e:
        print(f"Error adding video configurations to database: {e}")
        session.rollback() # Rollback in case of error during bulk add
        sys.exit(1)
    finally:
        session.close()
        print("Database session closed.")

    print("\nVideo import process completed successfully!")
    print(f"Processed {len(video_configs)} configurations from the Excel file.")

if __name__ == "__main__":
    # Create a dummy Excel for testing if it doesn't exist
    # This is helpful for quickly running the script
    dummy_excel_path_for_script = "data/dummy_videos_for_script.xlsx"
    if not os.path.exists(dummy_excel_path_for_script):
        if not os.path.exists("data"):
            os.makedirs("data")
        
        # Create dummy data similar to the one in importer.py for self-contained testing
        import pandas as pd
        dummy_data = {
            'Video Path': ['/script/video1.mp4', '/script/video2.avi', '/script/video3.mkv', '/path/to/video4.mp4'],
            'Video Name': ['Script Video 1', None, 'Script Video 3', 'Shared Video 4'],
            'Priority': [1, 2, 4, 5],
            'Enabled': [True, False, 'yes', 'no']
        }
        dummy_df = pd.DataFrame(dummy_data)
        dummy_df.to_excel(dummy_excel_path_for_script, index=False)
        print(f"Created dummy Excel file at '{dummy_excel_path_for_script}' for easy testing.")
        print(f"To run the script, you can use: python scripts/import_videos_from_excel.py {dummy_excel_path_for_script}")
    
    main()
