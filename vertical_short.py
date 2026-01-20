import subprocess
import cv2
from face_tracker import detect_face_box


def clamp(val, minv, maxv):
    return max(minv, min(val, maxv))


def create_vertical_short(
    input_video,
    output_video="shorts_ready.mp4"
):
    cap = cv2.VideoCapture(input_video)
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    x, y, w, h = detect_face_box(input_video)

    print("Face box:", x, y, w, h)
    print("Video size:", vw, vh)

    # --- layout ---
    OUT_W = 1080
    FACE_H = 720
    GAME_H = 1200

    # expand face region
    crop_w = int(w * 3)
    crop_h = int(h * 3)

    # clamp size
    crop_w = min(crop_w, vw)
    crop_h = min(crop_h, vh)

    crop_x = clamp(x + w // 2 - crop_w // 2, 0, vw - crop_w)
    crop_y = clamp(y + h // 2 - crop_h // 2, 0, vh - crop_h)

    filter_complex = (
        f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={OUT_W}:{FACE_H}[face];"
        f"[0:v]crop=in_w:in_h-{FACE_H}:0:{FACE_H},"
        f"scale={OUT_W}:{GAME_H}[game];"
        f"[face][game]vstack=inputs=2"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_video,
        "-filter_complex", filter_complex,
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_video
    ]

    print("Running FFmpeg...")
    subprocess.run(cmd, check=True)