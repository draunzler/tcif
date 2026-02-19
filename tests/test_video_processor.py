import pytest
import os
import subprocess
from app.video_processor import VideoProcessor


def test_video_processor_initialization():
    processor = VideoProcessor()
    assert processor.face_detection is not None


def test_video_processing_with_audio(tmp_path):
    """Test that video processing produces correct output with audio preserved."""
    processor = VideoProcessor()
    input_file = tmp_path / "input.mp4"
    output_file = tmp_path / "output.mp4"

    # Create a dummy 1280x720 video WITH an audio stream (3 seconds)
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=3:r=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(input_file)
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    assert os.path.exists(input_file)

    success = processor.process_video(str(input_file), str(output_file), "TestBroadcaster")

    assert success is True
    assert os.path.exists(output_file)
    assert os.path.getsize(output_file) > 0

    # Check output video resolution is 1080x1920
    res_result = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(output_file)
    ], capture_output=True, text=True, check=True)

    assert res_result.stdout.strip() == "1080x1920"

    # Check output has an audio stream
    audio_result = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(output_file)
    ], capture_output=True, text=True, check=True)

    assert audio_result.stdout.strip() == "audio"


def test_video_processing_no_input():
    """Test graceful failure when input file doesn't exist."""
    processor = VideoProcessor()
    success = processor.process_video("/nonexistent/video.mp4", "/tmp/output.mp4")
    assert success is False
