#!/usr/bin/env python3
"""
Object tracker node (single tick path, no DeepStream).

- Runs YOLO in a timer callback for both sim and real modes.
- Publishes /pixel_error (geometry_msgs/Point).
- Optionally streams annotated video over UDP using OpenCV+GStreamer writer.

Modes:
  --sim  : macOS camera index 0 (AVFoundation) by default.
  (default real): Linux /dev/video1 then /dev/video0.
"""

import os
import platform
import sys
import time
from pathlib import Path

import cv2
import rclpy
from dotenv import load_dotenv
from geometry_msgs.msg import Point
from rclpy.node import Node
from ultralytics import YOLO

CAMERA_DEVICE_CANDIDATES = ("/dev/video1", "/dev/video0")
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

load_dotenv()

LAPTOP_IP = os.getenv("LAPTOP_IP")
UDP_PORT = 5000
ENABLE_UDP_PREVIEW = True

IS_MAC = platform.system() == "Darwin"
USE_SIM = "--sim" in sys.argv
if USE_SIM:
    sys.argv.remove("--sim")

SIM_CAMERA_INDEX = int(os.environ.get("SIM_CAMERA_INDEX", "0"))
CAMERA_OPEN_RETRIES = 12
CAMERA_OPEN_RETRY_SLEEP_SEC = 0.25


MODEL_PATH_SIM = Path(os.getenv("MODEL_PATH_SIM", "models/sim_default.pt"))
MODEL_PATH_REAL = Path(os.getenv("MODEL_PATH_REAL", "models/real_default.pt"))


def _select_linux_camera_device() -> str:
    for device in CAMERA_DEVICE_CANDIDATES:
        if not os.path.exists(device):
            continue
        try:
            fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
            os.close(fd)
            return device
        except OSError:
            continue
    raise RuntimeError(
        f"No available camera device found in {CAMERA_DEVICE_CANDIDATES}"
    )


def _open_camera_with_warmup(
    camera_source,
    backend,
    label: str,
):
    cap = cv2.VideoCapture(camera_source, backend)
    if not cap.isOpened():
        return None, False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    for _ in range(CAMERA_OPEN_RETRIES):
        ok, frame = cap.read()
        if ok and frame is not None:
            return cap, True
        time.sleep(CAMERA_OPEN_RETRY_SLEEP_SEC)

    cap.release()
    return None, False


def _open_sim_camera_on_mac():
    # Continuity Camera / FaceTime cameras can need a few warm-up reads after
    # AVFoundation opens the device, especially when the camera has just been
    # activated by the OS. Try a few backends/indices before failing hard.
    candidates = [
        (SIM_CAMERA_INDEX, cv2.CAP_AVFOUNDATION, f"{SIM_CAMERA_INDEX} (AVFoundation)"),
        (SIM_CAMERA_INDEX, cv2.CAP_ANY, f"{SIM_CAMERA_INDEX} (default backend)"),
    ]
    if SIM_CAMERA_INDEX != 0:
        candidates.insert(0, (0, cv2.CAP_AVFOUNDATION, "0 (AVFoundation)"))
        candidates.insert(1, (0, cv2.CAP_ANY, "0 (default backend)"))

    for source, backend, label in candidates:
        cap, ok = _open_camera_with_warmup(source, backend, label)
        if ok:
            return cap, label

    raise RuntimeError(
        "Could not open a macOS sim camera. "
        "If you're using Continuity Camera, keep the iPhone awake/unlocked and "
        "set SIM_CAMERA_INDEX if needed."
    )


def _make_udp_writer(width: int, height: int, fps: int) -> cv2.VideoWriter:
    # OpenCV must be built with GStreamer support for this to open.
    pipeline = (
        "appsrc ! videoconvert ! "
        "x264enc tune=zerolatency speed-preset=ultrafast bitrate=800 key-int-max=30 ! "
        "rtph264pay pt=96 ! "
        f"udpsink host={LAPTOP_IP} port={UDP_PORT} sync=false async=false"
    )
    return cv2.VideoWriter(
        pipeline,
        cv2.CAP_GSTREAMER,
        0,
        float(fps),
        (int(width), int(height)),
        True,
    )


class TrackerNode(Node):
    def __init__(self):
        super().__init__("object_tracker_node")

        self.publisher_ = self.create_publisher(Point, "pixel_error", 10)
        self.msg = Point()
        self.msg.z = 0.0

        if USE_SIM and IS_MAC:
            self.cap, self.camera_device = _open_sim_camera_on_mac()
            model_path = MODEL_PATH_SIM
        elif USE_SIM:
            self.camera_device = _select_linux_camera_device()
            self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
            model_path = MODEL_PATH_SIM
        else:
            self.camera_device = _select_linux_camera_device()
            self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
            model_path = MODEL_PATH_REAL

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera ({self.camera_device})")

        ok, frame = self.cap.read()
        if not ok or frame is None:
            for _ in range(CAMERA_OPEN_RETRIES):
                time.sleep(CAMERA_OPEN_RETRY_SLEEP_SEC)
                ok, frame = self.cap.read()
                if ok and frame is not None:
                    break
            if not ok or frame is None:
                raise RuntimeError(
                    f"Camera opened but first frame read failed ({self.camera_device})"
                )

        self.frame_h, self.frame_w = frame.shape[:2]
        self.x_mid = self.frame_w / 2.0
        self.y_mid = self.frame_h / 2.0

        self.scale_x = CAMERA_WIDTH / float(self.frame_w)
        self.scale_y = CAMERA_HEIGHT / float(self.frame_h)

        self.model = YOLO(str(model_path))

        self.udp_writer = None
        if ENABLE_UDP_PREVIEW:
            self.udp_writer = _make_udp_writer(self.frame_w, self.frame_h, CAMERA_FPS)
            if self.udp_writer.isOpened():
                self.get_logger().info(
                    f"UDP preview enabled -> udp://{LAPTOP_IP}:{UDP_PORT}"
                )
            else:
                self.get_logger().warning(
                    "UDP preview requested but writer could not open"
                )
                self.udp_writer.release()
                self.udp_writer = None

        self.timer = self.create_timer(1.0 / CAMERA_FPS, self._tick)

        self.get_logger().info(
            f"YOLO tracker on {self.camera_device} @ {self.frame_w}x{self.frame_h}, "
            "publishing /pixel_error"
        )

    def _tick(self):
        ok, frame = self.cap.read()
        if not ok:
            return

        results = self.model(frame, verbose=False)
        boxes = results[0].boxes

        if len(boxes) > 0:
            best_idx = int(boxes.conf.argmax().item())
            best_box = boxes[best_idx]
            x1, y1, x2, y2 = best_box.xyxy[0].tolist()

            x_center = 0.5 * (x1 + x2)
            y_center = 0.5 * (y1 + y2)

            self.msg.x = float((self.x_mid - x_center) * self.scale_x)
            self.msg.y = float((self.y_mid - y_center) * self.scale_y)
            self.publisher_.publish(self.msg)

            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

        cv2.imshow("YOLO Tracker", frame)
        if self.udp_writer is not None:
            self.udp_writer.write(frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            rclpy.shutdown()

    def destroy_node(self):
        try:
            self.cap.release()
        except Exception:
            pass
        try:
            if self.udp_writer is not None:
                self.udp_writer.release()
        except Exception:
            pass
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = TrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
