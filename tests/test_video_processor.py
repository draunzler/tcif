import pytest
import os
import subprocess
from app.video_processor import VideoProcessor

def test_video_processor_initialization():
    processor = VideoProcessor()
    assert os.path.exists(processor.logo_path)
    assert os.path.exists(processor.font_path)

def test_video_processing_logic(tmp_path):
    # This test checks if ffmpeg command is constructed and runs (mocking input if necessary)
    # Since we can't easily generate a real mp4 here, we'll check if the command would fail gracefully
    # or use a small dummy file if possible.
    
    processor = VideoProcessor()
    input_file = tmp_path / "input.mp4"
    output_file = tmp_path / "output.mp4"
    
    # Create a dummy video file using ffmpeg
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=1", 
        "-pix_fmt", "yuv420p", str(input_file)
    ], check=True)
    
    assert os.path.exists(input_file)
    
    success = processor.process_video(str(input_file), str(output_file), "TestBroadcaster")
    
    assert success is True
    assert os.path.exists(output_file)
    
    # Check output resolution with ffprobe
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", 
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", 
        str(output_file)
    ], capture_output=True, text=True, check=True)
    
    assert result.stdout.strip() == "720x1280"
