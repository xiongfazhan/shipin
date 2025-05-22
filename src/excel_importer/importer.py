import pandas as pd
import os

def read_excel_config(file_path: str) -> list[dict]:
    """
    Reads video configurations from an Excel file.

    Args:
        file_path (str): The path to the Excel file.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a video configuration.
                    Returns an empty list if the file doesn't exist or an error occurs.
    """
    if not os.path.exists(file_path):
        print(f"Error: Excel file not found at {file_path}")
        return []

    try:
        df = pd.read_excel(file_path)
        
        # Define expected columns and their default values if missing
        # 'Video Path' is mandatory.
        # 'Video Name' can be derived from path if missing.
        # 'Priority' defaults to 3.
        # 'Enabled' defaults to True.
        
        configs = []
        for index, row in df.iterrows():
            config = {}
            
            # Video Path (Mandatory)
            if 'Video Path' not in row or pd.isna(row['Video Path']):
                print(f"Warning: Skipping row {index+2} due to missing 'Video Path'.")
                continue
            config['video_path'] = str(row['Video Path'])
            
            # Video Name (Optional, derive from path if missing)
            if 'Video Name' in row and not pd.isna(row['Video Name']):
                config['video_name'] = str(row['Video Name'])
            else:
                config['video_name'] = os.path.splitext(os.path.basename(config['video_path']))[0]
                
            # Priority (Optional, default 3)
            if 'Priority' in row and not pd.isna(row['Priority']):
                try:
                    config['priority'] = int(row['Priority'])
                except ValueError:
                    print(f"Warning: Invalid priority value for {config['video_path']} in row {index+2}. Using default (3).")
                    config['priority'] = 3
            else:
                config['priority'] = 3
                
            # Enabled (Optional, default True)
            if 'Enabled' in row and not pd.isna(row['Enabled']):
                if isinstance(row['Enabled'], bool):
                    config['enabled'] = row['Enabled']
                elif str(row['Enabled']).lower() in ['true', '1', 'yes']:
                    config['enabled'] = True
                elif str(row['Enabled']).lower() in ['false', '0', 'no']:
                    config['enabled'] = False
                else:
                    print(f"Warning: Invalid boolean value for 'Enabled' for {config['video_path']} in row {index+2}. Using default (True).")
                    config['enabled'] = True
            else:
                config['enabled'] = True
            
            # Add other default fields expected by the database model, if not directly from Excel
            config['processing_status'] = 'pending' # Default status

            configs.append(config)
            
        print(f"Successfully read {len(configs)} configurations from {file_path}")
        return configs
        
    except FileNotFoundError:
        print(f"Error: Excel file not found at {file_path}")
        return []
    except pd.errors.EmptyDataError:
        print(f"Error: Excel file at {file_path} is empty.")
        return []
    except Exception as e:
        print(f"An error occurred while reading the Excel file {file_path}: {e}")
        return []

if __name__ == '__main__':
    # Example Usage (assuming you have a dummy_videos.xlsx in data/ folder)
    # Create a dummy Excel for testing
    if not os.path.exists("data"):
        os.makedirs("data")
    
    dummy_data = {
        'Video Path': ['/path/to/video1.mp4', '/path/to/video2.avi', '/another/path/video3.mkv', None, '/path/to/video4.mp4'],
        'Video Name': ['First Video', None, 'Third Video Fun', 'No Path Video', 'Fourth Video'],
        'Priority': [1, 2, 'InvalidPriority', 4, 5],
        'Enabled': [True, False, 'yes', 'no', 'InvalidBoolean']
    }
    dummy_df = pd.DataFrame(dummy_data)
    dummy_excel_path = "data/dummy_videos.xlsx"
    dummy_df.to_excel(dummy_excel_path, index=False)
    
    print(f"Created dummy Excel file at {dummy_excel_path} for testing.")
    
    configs = read_excel_config(dummy_excel_path)
    if configs:
        print("\nRead configurations:")
        for cfg in configs:
            print(cfg)
    else:
        print("\nNo configurations read or an error occurred.")

    # Test with a non-existent file
    print("\nTesting with a non-existent file:")
    read_excel_config("data/non_existent_file.xlsx")

    # Test with an empty file
    empty_excel_path = "data/empty_videos.xlsx"
    pd.DataFrame().to_excel(empty_excel_path, index=False)
    print(f"\nCreated empty Excel file at {empty_excel_path} for testing.")
    read_excel_config(empty_excel_path)
    # os.remove(empty_excel_path) # Clean up

    # Test with a file having only headers
    header_only_excel_path = "data/header_only_videos.xlsx"
    pd.DataFrame(columns=['Video Path', 'Video Name', 'Priority', 'Enabled']).to_excel(header_only_excel_path, index=False)
    print(f"\nCreated header-only Excel file at {header_only_excel_path} for testing.")
    read_excel_config(header_only_excel_path)
    # os.remove(header_only_excel_path) # Clean up

    # Clean up dummy excel
    # os.remove(dummy_excel_path)
    print(f"\nNote: Dummy files created in 'data/' directory. Consider cleaning them up manually if not needed.")
