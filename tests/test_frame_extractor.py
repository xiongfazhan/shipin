import unittest
import cv2
import numpy as np
import os
import sys

# Adjust Python path to include 'src'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This is the project root
sys.path.append(parent_dir)

from src.processing_core.frame_extractor import extract_frames

# Configuration for the dummy video
DUMMY_VIDEO_DIR = os.path.join(parent_dir, "data") # Store dummy video in project's data folder
DUMMY_VIDEO_FILENAME = "test_video_for_extractor.mp4"
DUMMY_VIDEO_PATH = os.path.join(DUMMY_VIDEO_DIR, DUMMY_VIDEO_FILENAME)
DUMMY_VIDEO_FPS = 30.0
DUMMY_VIDEO_DURATION_SECONDS = 2 # Keep it short
DUMMY_VIDEO_WIDTH = 320
DUMMY_VIDEO_HEIGHT = 240
DUMMY_VIDEO_TOTAL_FRAMES = int(DUMMY_VIDEO_FPS * DUMMY_VIDEO_DURATION_SECONDS)

def create_dummy_video_for_tests(video_path, fps, duration_sec, width, height):
    """Helper function to create a dummy video for testing."""
    if not os.path.exists(os.path.dirname(video_path)):
        os.makedirs(os.path.dirname(video_path))
    
    num_frames = int(fps * duration_sec)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"ERROR (test setup): Could not open VideoWriter for path {video_path}")
        return False

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(frame, f"F:{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)
    out.release()
    print(f"INFO (test setup): Dummy video created at {video_path} ({num_frames} frames, {fps} FPS)")
    return True

class TestFrameExtractor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a dummy video once for all tests in this class."""
        print(f"INFO (TestFrameExtractor): Setting up class. Attempting to create dummy video: {DUMMY_VIDEO_PATH}")
        if not create_dummy_video_for_tests(DUMMY_VIDEO_PATH, DUMMY_VIDEO_FPS, DUMMY_VIDEO_DURATION_SECONDS, DUMMY_VIDEO_WIDTH, DUMMY_VIDEO_HEIGHT):
            raise RuntimeError(f"Failed to create dummy video for tests at {DUMMY_VIDEO_PATH}. Tests cannot proceed.")
        print(f"INFO (TestFrameExtractor): Dummy video available at {DUMMY_VIDEO_PATH}")


    @classmethod
    def tearDownClass(cls):
        """Clean up the dummy video file after all tests."""
        print(f"INFO (TestFrameExtractor): Tearing down class. Attempting to remove dummy video: {DUMMY_VIDEO_PATH}")
        if os.path.exists(DUMMY_VIDEO_PATH):
            try:
                os.remove(DUMMY_VIDEO_PATH)
                print(f"INFO (TestFrameExtractor): Dummy video {DUMMY_VIDEO_PATH} removed successfully.")
            except OSError as e:
                print(f"WARNING (TestFrameExtractor): Could not remove dummy video {DUMMY_VIDEO_PATH}: {e}")
        else:
            print(f"INFO (TestFrameExtractor): Dummy video {DUMMY_VIDEO_PATH} was not found, no need to remove.")


    def test_extract_frames_valid_video_1fps_target(self):
        """Test with a valid video and a target of 1 FPS."""
        target_fps = 1.0
        # Expected frames: video_duration_seconds * target_fps
        # Stride = video_fps / target_fps = 30 / 1 = 30.
        # Frames selected: 0, 30. (Total 2 frames for a 2-second video)
        expected_frames = int(DUMMY_VIDEO_DURATION_SECONDS * target_fps) 
        
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=target_fps)
        self.assertEqual(len(frames), expected_frames, f"Expected {expected_frames} frames for {target_fps} FPS target, got {len(frames)}")
        for frame in frames:
            self.assertIsInstance(frame, np.ndarray, "Each frame should be a NumPy array.")
            self.assertEqual(frame.shape, (DUMMY_VIDEO_HEIGHT, DUMMY_VIDEO_WIDTH, 3), "Frame dimensions are incorrect.")

    def test_extract_frames_target_fps_higher_than_video_fps(self):
        """Test when target FPS is higher than the video's actual FPS."""
        target_fps = DUMMY_VIDEO_FPS * 2 # e.g., 60 FPS target for 30 FPS video
        # Expected: all frames from the video
        expected_frames = DUMMY_VIDEO_TOTAL_FRAMES
        
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=target_fps)
        self.assertEqual(len(frames), expected_frames, f"Expected all {expected_frames} frames when target FPS > video FPS, got {len(frames)}")

    def test_extract_frames_target_fps_equals_video_fps(self):
        """Test when target FPS is equal to the video's actual FPS."""
        target_fps = DUMMY_VIDEO_FPS 
        expected_frames = DUMMY_VIDEO_TOTAL_FRAMES
        
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=target_fps)
        self.assertEqual(len(frames), expected_frames, f"Expected all {expected_frames} frames when target FPS == video FPS, got {len(frames)}")

    def test_extract_frames_target_fps_half_video_fps(self):
        """Test with target FPS being half of the video's actual FPS."""
        target_fps = DUMMY_VIDEO_FPS / 2.0 # e.g., 15 FPS for a 30 FPS video
        # Stride = DUMMY_VIDEO_FPS / target_fps = 30 / 15 = 2
        # Expected frames: DUMMY_VIDEO_TOTAL_FRAMES / 2
        expected_frames = int(DUMMY_VIDEO_TOTAL_FRAMES / 2)
        
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=target_fps)
        self.assertEqual(len(frames), expected_frames, f"Expected {expected_frames} frames for {target_fps} FPS target, got {len(frames)}")

    def test_extract_frames_invalid_video_path(self):
        """Test with an invalid video path."""
        frames = extract_frames("non_existent_path/non_existent_video.mp4", frames_per_second_target=1.0)
        self.assertEqual(len(frames), 0, "Expected an empty list for an invalid video path.")

    def test_extract_frames_target_fps_zero(self):
        """Test with frames_per_second_target set to 0."""
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=0.0)
        self.assertEqual(len(frames), 0, "Expected an empty list when target FPS is 0.")

    def test_extract_frames_target_fps_negative(self):
        """Test with frames_per_second_target set to a negative value."""
        frames = extract_frames(DUMMY_VIDEO_PATH, frames_per_second_target=-5.0)
        self.assertEqual(len(frames), 0, "Expected an empty list when target FPS is negative.")

    # Potential edge case: video with 0 FPS or 0 total frames (if such a file can exist and be opened)
    # OpenCV might handle these internally, but good to be aware.
    # The current extract_frames has checks for video_fps <= 0 and total_frames <= 0.

if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # e.g., python tests/test_frame_extractor.py
    print("Running tests for Frame Extractor...")
    unittest.main(verbosity=2)
