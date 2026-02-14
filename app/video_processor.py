import subprocess
import os
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.logo_path = "/home/draunzler/Desktop/tcif/static/images/Twitch-Logo-PNG-Clip-Art-HD-Quality.png"
        self.font_path = "/home/draunzler/Desktop/tcif/static/fonts/twitch.otf"
        self.font_color = "0x6441A5"  # FFmpeg uses 0xRRGGBB

    def process_video(self, input_path: str, output_path: str, broadcaster_name: str) -> bool:
        """
        Converts video to 9:16 720p and overlays Twitch logo and broadcaster name.
        Position: Centered horizontally, 40% from the bottom.
        """
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        # FFmpeg filter string
        # 1. Scale and crop to 9:16 (720x1280)
        # 2. Overlay logo
        # 3. Draw text
        
        # We need to escape the broadcaster name for drawtext
        safe_name = broadcaster_name.replace("'", "\\'").replace(":", "\\:")
        
        # Horizontal center: (w-overlay_w)/2
        # Vertical 40% from bottom: h - (h * 0.4) - overlay_h
        
        filter_complex = (
            f"scale=ih*9/16:ih,scale=720:1280,setsar=1,"
            f"movie='{self.logo_path}' [logo];"
            f"[0:v][logo] overlay=(W-w)/2:H-(H*0.4)-h [overlaid];"
            f"[overlaid] drawtext=fontfile='{self.font_path}':text='{safe_name}':"
            f"fontcolor={self.font_color}:fontsize=48:x=(w-text_w)/2:y=H-(H*0.4)+20"
        )

        command = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-c:a", "copy",  # Copy audio stream
            output_path
        ]

        try:
            logger.info(f"Processing video: {input_path} -> {output_path}")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during video processing: {e}")
            return False

if __name__ == "__main__":
    # Test run if executed directly
    logging.basicConfig(level=logging.INFO)
    processor = VideoProcessor()
    # Replace with an actual file path for local testing
    # processor.process_video("input.mp4", "output.mp4", "BroadcasterName")
