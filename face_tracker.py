import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def detect_face_box(video_path):
    cap = cv2.VideoCapture(video_path)

    base_options = python.BaseOptions(
        model_asset_path="face_detector.tflite"
    )

    options = vision.FaceDetectorOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO
    )

    detector = vision.FaceDetector.create_from_options(options)

    boxes = []
    frame_index = 0
    fps = cap.get(cv2.CAP_PROP_FPS)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp = int((frame_index / fps) * 1000)

        result = detector.detect_for_video(mp_image, timestamp)

        if result.detections:
            box = result.detections[0].bounding_box
            boxes.append(
                (box.origin_x, box.origin_y, box.width, box.height)
            )

        frame_index += 10
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

    cap.release()
    detector.close()

    if not boxes:
        raise RuntimeError("No face detected in video.")

    return tuple(np.mean(boxes, axis=0).astype(int))