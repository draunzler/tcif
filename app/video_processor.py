import cv2
import numpy as np
import mediapipe as mp
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

# Vertical output size (Shorts format)
OUT_W = 1080
OUT_H = 1920

# 35% for facecam, 65% for gameplay
TOP_H = int(OUT_H * 0.35)
BOTTOM_H = int(OUT_H * 0.65)


class VideoProcessor:
    def __init__(self):
        """Initialize MediaPipe Face Detection"""
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        )

    def process_video(self, input_path: str, output_path: str, broadcaster_name: str = None) -> bool:
        """
        Process video to create YouTube Shorts (1080x1920).
        
        If a face is detected in the first frame:
        - Top 35%: Facecam (cropped and resized)
        - Bottom 65%: Gameplay (centered)
        
        If no face is detected:
        - Top 17.5%: Blurred gameplay
        - Middle 65%: Clear centered gameplay
        - Bottom 17.5%: Blurred gameplay
        
        Args:
            input_path: Path to input video file
            output_path: Path to output video file
            broadcaster_name: Optional broadcaster name (currently unused)
        
        Returns:
            True if processing successful, False otherwise
        """
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        # Create temporary video-only file (without audio)
        temp_video_path = output_path.replace(".mp4", "_temp_no_audio.mp4")

        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                logger.error(f"Cannot open input video: {input_path}")
                return False

            fps = cap.get(cv2.CAP_PROP_FPS)

            # Detect face in the first frame only
            ret, first_frame = cap.read()
            if not ret:
                logger.error("Cannot read first frame from video")
                cap.release()
                return False

            h, w, _ = first_frame.shape
            face_region = None

            # Convert to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            results = self.face_detection.process(rgb_frame)

            if results.detections:
                # Get the first detected face
                detection = results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                
                # Convert relative coordinates to absolute pixels
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                bw = int(bbox.width * w)
                bh = int(bbox.height * h)
                
                # Add padding around face
                pad = int(bh * 1.5)
                cx = x + bw // 2
                cy = y + bh // 2
                
                fx1 = max(0, cx - pad)
                fy1 = max(0, cy - pad)
                fx2 = min(w, cx + pad)
                fy2 = min(h, cy + pad)
                
                face_region = (fx1, fy1, fx2, fy2)
                logger.info(f"Face detected at: x={x}, y={y}, w={bw}, h={bh}")
            else:
                logger.info("No face detected in first frame. Using full-screen gameplay mode.")

            # Determine output dimensions based on face detection
            if face_region:
                # Face detected: use 35:65 split
                out_h = OUT_H
                top_h = TOP_H
                bottom_h = BOTTOM_H
            else:
                # No face: full-screen gameplay
                out_h = OUT_H
                top_h = 0
                bottom_h = OUT_H

            # Create video writer with H264 codec for better compatibility
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
            out = cv2.VideoWriter(temp_video_path, fourcc, fps, (OUT_W, out_h))

            if not out.isOpened():
                logger.error(f"Cannot create output video: {temp_video_path}")
                cap.release()
                return False

            # Reset video to beginning
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                h, w, _ = frame.shape
                
                if face_region:
                    # Extract face region (static position from first frame)
                    fx1, fy1, fx2, fy2 = face_region
                    face_crop = frame[fy1:fy2, fx1:fx2]
                    
                    # Resize maintaining aspect ratio, then center-crop to fit
                    crop_h, crop_w = face_crop.shape[:2]
                    target_aspect = OUT_W / top_h
                    crop_aspect = crop_w / crop_h
                    
                    if crop_aspect > target_aspect:
                        # Crop is wider, fit to height
                        new_h = top_h
                        new_w = int(crop_w * (top_h / crop_h))
                        resized = cv2.resize(face_crop, (new_w, new_h))
                        # Center crop width
                        start_x = (new_w - OUT_W) // 2
                        face_crop = resized[:, start_x:start_x + OUT_W]
                    else:
                        # Crop is taller, fit to width
                        new_w = OUT_W
                        new_h = int(crop_h * (OUT_W / crop_w))
                        resized = cv2.resize(face_crop, (new_w, new_h))
                        # Center crop height
                        start_y = (new_h - top_h) // 2
                        face_crop = resized[start_y:start_y + top_h, :]
                    
                    # Extract centered gameplay region
                    gx1 = max(0, w // 2 - w // 4)
                    gx2 = min(w, w // 2 + w // 4)
                    gameplay = frame[:, gx1:gx2]
                    gameplay = cv2.resize(gameplay, (OUT_W, bottom_h))
                    
                    # Stack top + bottom
                    final = np.vstack([face_crop, gameplay])
                else:
                    # No face: centered gameplay (65%) with blurred top and bottom
                    gx1 = max(0, w // 2 - w // 4)
                    gx2 = min(w, w // 2 + w // 4)
                    gameplay = frame[:, gx1:gx2]
                    
                    # Resize gameplay to 65% of output height
                    gameplay_h = int(OUT_H * 0.65)
                    gameplay_resized = cv2.resize(gameplay, (OUT_W, gameplay_h))
                    
                    # Create blurred versions for top and bottom
                    blur_h = int(OUT_H * 0.175)  # 17.5% each for top and bottom
                    
                    # Apply strong Gaussian blur
                    blurred_gameplay = cv2.GaussianBlur(gameplay_resized, (51, 51), 30)
                    
                    # Extract top and bottom portions from blurred gameplay
                    top_blur = blurred_gameplay[:blur_h, :]
                    bottom_blur = blurred_gameplay[-blur_h:, :]
                    
                    # Stack: blurred_top + clear_gameplay + blurred_bottom
                    final = np.vstack([top_blur, gameplay_resized, bottom_blur])
                
                out.write(final)
                
                if frame_count % 100 == 0:
                    logger.info(f"Processed {frame_count} frames...")

            cap.release()
            out.release()
            logger.info(f"Video frames processed: {frame_count} frames")

            # Now merge the processed video with the original audio using ffmpeg
            logger.info(f"Merging audio from original video...")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', temp_video_path,  # Video input (no audio)
                '-i', input_path,  # Original video with audio
                '-map', '0:v:0',  # Take video from first input
                '-map', '1:a:0?',  # Take audio from second input (? makes it optional)
                '-c:v', 'libx264',  # H.264 video codec for YouTube
                '-preset', 'medium',  # Encoding speed/quality tradeoff
                '-crf', '23',  # Quality (lower is better, 18-28 is reasonable)
                '-c:a', 'aac',  # AAC audio codec for YouTube
                '-b:a', '192k',  # Audio bitrate
                '-shortest',  # Match the shortest stream duration
                output_path
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully merged audio! Output: {output_path}")
                
                # Clean up temporary file
                try:
                    os.remove(temp_video_path)
                    logger.info(f"Cleaned up temporary file: {temp_video_path}")
                except Exception as e:
                    logger.warning(f"Could not remove temporary file: {e}")
                
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                logger.warning(f"Keeping temp file for inspection: {temp_video_path}")
                return False

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return False
        finally:
            # Ensure resources are cleaned up
            if hasattr(self, 'face_detection'):
                self.face_detection.close()



if __name__ == "__main__":
    # Test run if executed directly
    logging.basicConfig(level=logging.INFO)
    processor = VideoProcessor()
    # Replace with an actual file path for local testing
    # processor.process_video("input.mp4", "output.mp4", "BroadcasterName")
