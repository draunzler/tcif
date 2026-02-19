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
TOP_H = int(OUT_H * 0.35)   # 672
BOTTOM_H = OUT_H - TOP_H    # 1248


class VideoProcessor:
    def __init__(self):
        """Initialize MediaPipe Face Detection"""
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        )

    def _get_video_info(self, input_path: str) -> dict:
        """Get video info (fps, has_audio) using ffprobe."""
        # Get FPS
        fps_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_path
        ]
        fps_result = subprocess.run(fps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        fps_str = fps_result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str) if fps_str else 30.0

        # Check for audio stream
        audio_cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_type',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_path
        ]
        audio_result = subprocess.run(audio_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        has_audio = audio_result.stdout.strip() == 'audio'

        return {'fps': fps, 'has_audio': has_audio}

    def _detect_face_region(self, frame: np.ndarray) -> tuple | None:
        """
        Detect face in a frame using MediaPipe.
        Returns (fx1, fy1, fx2, fy2) bounding box with padding, or None.
        """
        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)

        if not results.detections:
            return None

        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box

        # Convert relative coordinates to absolute pixels
        x = int(bbox.xmin * w)
        y = int(bbox.ymin * h)
        bw = int(bbox.width * w)
        bh = int(bbox.height * h)

        # Add generous padding around the face
        pad = int(bh * 1.5)
        cx = x + bw // 2
        cy = y + bh // 2

        fx1 = max(0, cx - pad)
        fy1 = max(0, cy - pad)
        fx2 = min(w, cx + pad)
        fy2 = min(h, cy + pad)

        logger.info(f"Face detected at: x={x}, y={y}, w={bw}, h={bh} → crop=({fx1},{fy1})-({fx2},{fy2})")
        return (fx1, fy1, fx2, fy2)

    def _compose_frame_with_face(self, frame: np.ndarray, face_region: tuple) -> np.ndarray:
        """
        Compose a vertical frame with face on top (35%) and gameplay on bottom (65%).
        """
        h, w = frame.shape[:2]
        fx1, fy1, fx2, fy2 = face_region

        # --- Top panel: face crop ---
        face_crop = frame[fy1:fy2, fx1:fx2]
        crop_h, crop_w = face_crop.shape[:2]

        # Resize to fill TOP_H x OUT_W, preserving aspect ratio then center-cropping
        target_aspect = OUT_W / TOP_H
        crop_aspect = crop_w / crop_h

        if crop_aspect > target_aspect:
            # Wider than needed → fit height, crop width
            new_h = TOP_H
            new_w = int(crop_w * (TOP_H / crop_h))
            resized = cv2.resize(face_crop, (new_w, new_h))
            sx = (new_w - OUT_W) // 2
            face_panel = resized[:, sx:sx + OUT_W]
        else:
            # Taller than needed → fit width, crop height
            new_w = OUT_W
            new_h = int(crop_h * (OUT_W / crop_w))
            resized = cv2.resize(face_crop, (new_w, new_h))
            sy = (new_h - TOP_H) // 2
            face_panel = resized[sy:sy + TOP_H, :]

        # --- Bottom panel: zoomed gameplay ---
        # Take center 50% width of the frame for a zoomed-in gameplay view
        gx1 = w // 4
        gx2 = w - w // 4
        gameplay = frame[:, gx1:gx2]
        gameplay_panel = cv2.resize(gameplay, (OUT_W, BOTTOM_H))

        return np.vstack([face_panel, gameplay_panel])

    def _compose_frame_no_face(self, frame: np.ndarray) -> np.ndarray:
        """
        Compose a vertical frame with blurred bars + centered gameplay (no face detected).
        """
        h, w = frame.shape[:2]

        # Take center 50% width for zoomed gameplay
        gx1 = w // 4
        gx2 = w - w // 4
        gameplay = frame[:, gx1:gx2]

        # Main gameplay area (65% of output)
        gameplay_h = int(OUT_H * 0.65)
        gameplay_resized = cv2.resize(gameplay, (OUT_W, gameplay_h))

        # Blurred bars for top and bottom (17.5% each)
        blur_h = (OUT_H - gameplay_h) // 2

        # Create a full-width blurred version of the frame
        full_resized = cv2.resize(frame, (OUT_W, OUT_H))
        blurred = cv2.GaussianBlur(full_resized, (51, 51), 30)

        top_bar = blurred[:blur_h, :]
        remaining_h = OUT_H - blur_h - gameplay_h
        bottom_bar = blurred[OUT_H - remaining_h:, :]

        return np.vstack([top_bar, gameplay_resized, bottom_bar])

    def process_video(self, input_path: str, output_path: str, broadcaster_name: str = None) -> bool:
        """
        Process video to create YouTube Shorts (1080x1920).

        Uses ffmpeg subprocess pipe for encoding instead of OpenCV VideoWriter
        to avoid corrupted output files and audio issues.

        If a face is detected in the first frame:
        - Top 35%: Facecam (cropped and resized)
        - Bottom 65%: Gameplay (centered and zoomed)

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

        cap = None
        ffmpeg_proc = None

        try:
            # --- Step 1: Get video info via ffprobe ---
            info = self._get_video_info(input_path)
            fps = info['fps']
            has_audio = info['has_audio']
            logger.info(f"Input video: fps={fps:.2f}, has_audio={has_audio}")

            # --- Step 2: Open input with OpenCV for frame reading ---
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                logger.error(f"Cannot open input video: {input_path}")
                return False

            # --- Step 3: Detect face in first frame ---
            ret, first_frame = cap.read()
            if not ret:
                logger.error("Cannot read first frame from video")
                return False

            face_region = self._detect_face_region(first_frame)
            if face_region:
                logger.info("Face detected — using 35/65 split (face top, gameplay bottom)")
            else:
                logger.info("No face detected — using full-screen gameplay with blurred bars")

            # Reset to beginning
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # --- Step 4: Build ffmpeg command to receive raw frames via stdin ---
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                # Raw video input from stdin
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{OUT_W}x{OUT_H}',
                '-r', str(fps),
                '-i', 'pipe:0',
            ]

            if has_audio:
                # Second input: original file for audio
                ffmpeg_cmd.extend(['-i', input_path])

            # Output mappings
            ffmpeg_cmd.extend(['-map', '0:v:0'])
            if has_audio:
                ffmpeg_cmd.extend(['-map', '1:a:0'])

            # Video encoding — H.264 with yuv420p for maximum compatibility
            ffmpeg_cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
            ])

            if has_audio:
                # Audio encoding — AAC for YouTube compatibility
                ffmpeg_cmd.extend([
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-ar', '44100',
                ])

            ffmpeg_cmd.extend([
                '-movflags', '+faststart',       # Enable streaming-friendly MP4
                '-avoid_negative_ts', 'make_zero',
                '-shortest',
                output_path
            ])

            logger.info(f"Starting ffmpeg pipe: {' '.join(ffmpeg_cmd)}")

            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # --- Step 5: Read frames, compose, and pipe to ffmpeg ---
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                if face_region:
                    final = self._compose_frame_with_face(frame, face_region)
                else:
                    final = self._compose_frame_no_face(frame)

                # Write raw BGR bytes to ffmpeg stdin
                try:
                    ffmpeg_proc.stdin.write(final.tobytes())
                except BrokenPipeError:
                    logger.error("FFmpeg pipe broke — ffmpeg likely crashed")
                    break

                if frame_count % 300 == 0:
                    logger.info(f"Processed {frame_count} frames...")

            # Close stdin to signal end of input
            ffmpeg_proc.stdin.close()
            cap.release()
            cap = None

            # Wait for ffmpeg to finish
            stdout, stderr = ffmpeg_proc.communicate()
            ffmpeg_proc = None

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"✅ Successfully created output video: {output_path}")
                logger.info(f"   Processed {frame_count} frames at {fps:.1f} fps")
                if has_audio:
                    logger.info(f"✅ Audio included (AAC 192k, 44100 Hz)")
                else:
                    logger.warning(f"⚠️ Video created without audio (source had no audio)")
                return True
            else:
                logger.error(f"❌ FFmpeg failed to produce output file")
                logger.error(f"FFmpeg stderr:\n{stderr.decode('utf-8', errors='replace')}")
                return False

        except Exception as e:
            logger.error(f"Error processing video: {e}", exc_info=True)
            return False
        finally:
            if cap is not None:
                cap.release()
            if ffmpeg_proc is not None:
                try:
                    ffmpeg_proc.stdin.close()
                except Exception:
                    pass
                ffmpeg_proc.wait()
