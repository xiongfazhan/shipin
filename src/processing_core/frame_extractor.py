import cv2
import numpy as np
import os

def extract_frames(video_path: str, frames_per_second_target: float = 1.0) -> list[np.ndarray]:
    """
    Extracts frames from a video file based on a target frames per second.

    Args:
        video_path (str): The path to the video file.
        frames_per_second_target (float): The desired number of frames to extract per second of video.
                                          If 0 or negative, returns an empty list.
                                          If higher than video's actual FPS, all frames are extracted.

    Returns:
        list[np.ndarray]: A list of extracted frames (as NumPy arrays).
                          Returns an empty list if an error occurs or target FPS is <= 0.
    """
    extracted_frames = []

    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return extracted_frames

    if frames_per_second_target <= 0:
        print(f"Info: Target FPS is {frames_per_second_target}. Returning no frames.")
        return extracted_frames

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return extracted_frames

    try:
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0: # Should not happen for valid videos, but good to check
            print(f"Error: Video FPS ({video_fps}) is not valid. Cannot extract frames.")
            return extracted_frames
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
             print(f"Warning: Video {video_path} reported 0 or negative total frames. Proceeding frame by frame.")
             # Allow proceeding, will stop when cap.read() fails

        # Calculate frame stride
        # If target FPS is higher than video FPS, take every frame (stride = 1)
        # Otherwise, calculate stride to match target FPS
        if frames_per_second_target >= video_fps:
            frame_stride = 1
        else:
            frame_stride = round(video_fps / frames_per_second_target)
            if frame_stride < 1: # Ensure stride is at least 1
                frame_stride = 1
        
        print(f"Video: {os.path.basename(video_path)}, Original FPS: {video_fps:.2f}, Target FPS: {frames_per_second_target:.2f}, Frame Stride: {frame_stride}")

        frame_count = 0
        selected_frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break # End of video or error reading frame

            if frame_count % frame_stride == 0:
                extracted_frames.append(frame)
                selected_frame_count += 1
            
            frame_count += 1
        
        print(f"Successfully extracted {selected_frame_count} frames from {video_path}.")

    except Exception as e:
        print(f"An error occurred during frame extraction from {video_path}: {e}")
        # Return whatever was extracted so far, or an empty list if error was early
    finally:
        cap.release()
        print(f"Released video capture for {video_path}.")
    
    return extracted_frames

if __name__ == '__main__':
    print("Running Frame Extractor Example...")
    # Create a dummy video for testing if it doesn't exist in a 'data' directory
    # This part requires opencv-python to be installed.
    
    data_dir = "data" # Assuming a 'data' directory in the project root
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    dummy_video_path = os.path.join(data_dir, "dummy_test_video.mp4")
    
    # Check if dummy video needs to be created
    if not os.path.exists(dummy_video_path):
        print(f"Creating dummy video at {dummy_video_path} for testing...")
        # Video properties
        width, height = 640, 480
        fps_video = 30.0
        duration_seconds = 3
        num_frames = int(fps_video * duration_seconds)

        # Define the codec and create VideoWriter object
        # Using 'mp4v' for MP4, check fourcc.org for more. 'XVID' for .avi
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        out = cv2.VideoWriter(dummy_video_path, fourcc, fps_video, (width, height))

        if not out.isOpened():
            print(f"Error: Could not open VideoWriter for path {dummy_video_path}. Check codec or permissions.")
        else:
            for i in range(num_frames):
                # Create a simple frame: black background with frame number
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                text = f"Frame: {i+1}"
                cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                out.write(frame)
            out.release()
            print(f"Dummy video created successfully with {num_frames} frames at {fps_video} FPS.")

    # Test cases
    print("\n--- Test Case 1: Valid video, 1 FPS target ---")
    if os.path.exists(dummy_video_path):
        frames_1fps = extract_frames(dummy_video_path, frames_per_second_target=1.0)
        # Expected: 3 seconds * 1 FPS = 3 frames (approx, due to rounding and frame selection)
        print(f"Extracted {len(frames_1fps)} frames for 1 FPS target.")
        # For a 30fps video of 3s (90 frames), stride will be 30. Frames 0, 30, 60 will be selected. So 3 frames.
    else:
        print(f"Skipping Test Case 1 as dummy video {dummy_video_path} was not found/created.")

    print("\n--- Test Case 2: Valid video, 0.5 FPS target ---")
    if os.path.exists(dummy_video_path):
        frames_half_fps = extract_frames(dummy_video_path, frames_per_second_target=0.5)
        # Expected: 3 seconds * 0.5 FPS = 1.5, so 1 or 2 frames.
        # Stride for 30 FPS video and 0.5 target: 30 / 0.5 = 60. Frames 0, 60. So 2 frames.
        print(f"Extracted {len(frames_half_fps)} frames for 0.5 FPS target.")
    else:
        print(f"Skipping Test Case 2 as dummy video {dummy_video_path} was not found/created.")

    print("\n--- Test Case 3: Valid video, target FPS > video FPS (e.g., 60 FPS target for 30 FPS video) ---")
    if os.path.exists(dummy_video_path):
        frames_all = extract_frames(dummy_video_path, frames_per_second_target=60.0)
        # Expected: all frames (approx 90 for a 3s, 30fps video)
        print(f"Extracted {len(frames_all)} frames when target FPS > video FPS.")
    else:
        print(f"Skipping Test Case 3 as dummy video {dummy_video_path} was not found/created.")

    print("\n--- Test Case 4: Invalid video path ---")
    frames_invalid_path = extract_frames("non_existent_video.mp4", frames_per_second_target=1.0)
    print(f"Extracted {len(frames_invalid_path)} frames for invalid path (expected 0).")

    print("\n--- Test Case 5: Target FPS = 0 ---")
    if os.path.exists(dummy_video_path):
        frames_zero_fps = extract_frames(dummy_video_path, frames_per_second_target=0)
        print(f"Extracted {len(frames_zero_fps)} frames for 0 FPS target (expected 0).")
    else:
        print(f"Skipping Test Case 5 as dummy video {dummy_video_path} was not found/created.")
        
    print("\n--- Test Case 6: Target FPS < 0 ---")
    if os.path.exists(dummy_video_path):
        frames_neg_fps = extract_frames(dummy_video_path, frames_per_second_target=-1.0)
        print(f"Extracted {len(frames_neg_fps)} frames for negative FPS target (expected 0).")
    else:
        print(f"Skipping Test Case 6 as dummy video {dummy_video_path} was not found/created.")

    # Consider cleaning up dummy_video_path if needed, or leave for manual inspection
    # print(f"\nNote: A dummy video '{dummy_video_path}' may have been created/used for testing.")
