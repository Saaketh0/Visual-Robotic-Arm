#!/usr/bin/env python3
import os
import platform

# Workaround for macOS Accelerate / NumPy linkage issues in some conda environments.
# Must be set before importing numpy (cv2 imports numpy).
if platform.system() == "Darwin":
    os.environ["NPY_DISABLE_CPU_FEATURES"] = "accelerate"

import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import rclpy
from dotenv import load_dotenv
from geometry_msgs.msg import Point
from rclpy.node import Node

from xarm_runtime.onnx_inference import create_detector
from xarm_runtime.ros_runtime import SHUTDOWN_EXCEPTIONS, request_shutdown, shutdown_node
from xarm_runtime.tracker_config import (
    UDP_PORT,
    DetectionBox,
    build_runtime_config,
    compute_pixel_error,
    require_existing_model,
    select_linux_camera_device,
)

CAMERA_OPEN_RETRIES = 12
CAMERA_OPEN_RETRY_SLEEP_SEC = 0.25

load_dotenv()

IS_MAC = platform.system() == "Darwin"
USE_SIM = "--sim" in sys.argv
if USE_SIM:
    sys.argv.remove("--sim")

_WORKSPACE_ROOT = Path(os.environ.get("XARM_WS_ROOT", str(Path.cwd())))


def open_camera_with_warmup(camera_source, backend, width: int, height: int, fps: int):
    cap = cv2.VideoCapture(camera_source, backend)
    if not cap.isOpened():
        return None, False
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    for _ in range(CAMERA_OPEN_RETRIES):
        ok, frame = cap.read()
        if ok and frame is not None:
            return cap, True
        time.sleep(CAMERA_OPEN_RETRY_SLEEP_SEC)
    cap.release()
    return None, False


def open_sim_camera_on_mac(sim_camera_index: int, width: int, height: int, fps: int):
    candidates = [
        (sim_camera_index, cv2.CAP_AVFOUNDATION),
        (sim_camera_index, cv2.CAP_ANY),
    ]
    if sim_camera_index != 0:
        candidates.insert(0, (0, cv2.CAP_AVFOUNDATION))
        candidates.insert(1, (0, cv2.CAP_ANY))
    for source, backend in candidates:
        cap, ok = open_camera_with_warmup(source, backend, width, height, fps)
        if ok:
            return cap, str(source)
    raise RuntimeError(
        "Could not open a macOS sim camera. If using Continuity Camera, keep the device awake/unlocked and set SIM_CAMERA_INDEX if needed."
    )


def make_udp_writer(width: int, height: int, fps: int, laptop_ip: Optional[str]):
    pipeline = (
        "appsrc ! videoconvert ! "
        "x264enc tune=zerolatency speed-preset=ultrafast bitrate=800 key-int-max=30 ! "
        "rtph264pay pt=96 ! "
        f"udpsink host={laptop_ip} port={UDP_PORT} sync=false async=false"
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
        self._declare_runtime_parameters()
        self.runtime_config = build_runtime_config(_WORKSPACE_ROOT, USE_SIM, IS_MAC, self._runtime_parameters())
        self.publisher_ = self.create_publisher(Point, "pixel_error", 10)
        self.msg = Point()
        self.msg.z = 0.0

        if self.runtime_config.use_sim and self.runtime_config.is_mac:
            self.cap, self.camera_device = open_sim_camera_on_mac(
                self.runtime_config.sim_camera_index,
                self.runtime_config.camera_width,
                self.runtime_config.camera_height,
                self.runtime_config.camera_fps,
            )
            model_path = self.runtime_config.model_path_sim
        elif self.runtime_config.use_sim:
            self.camera_device = select_linux_camera_device(self.runtime_config.camera_device_candidates)
            self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
            model_path = self.runtime_config.model_path_sim
        else:
            if self.runtime_config.is_mac:
                self.cap, self.camera_device = open_sim_camera_on_mac(
                    self.runtime_config.sim_camera_index,
                    self.runtime_config.camera_width,
                    self.runtime_config.camera_height,
                    self.runtime_config.camera_fps,
                )
            else:
                self.camera_device = select_linux_camera_device(self.runtime_config.camera_device_candidates)
                self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
            model_path = self.runtime_config.model_path_real

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.runtime_config.camera_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.runtime_config.camera_height)
        self.cap.set(cv2.CAP_PROP_FPS, self.runtime_config.camera_fps)
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
                raise RuntimeError(f"Camera opened but first frame read failed ({self.camera_device})")

        self.frame_h, self.frame_w = frame.shape[:2]
        model_mode = "sim" if self.runtime_config.use_sim else "real"
        model_path = require_existing_model(model_path, model_mode)
        self.detector = create_detector(model_path)
        self.udp_writer = None
        if self.runtime_config.enable_udp_preview:
            self.udp_writer = make_udp_writer(
                self.frame_w, self.frame_h, self.runtime_config.camera_fps, self.runtime_config.laptop_ip
            )
            if self.udp_writer.isOpened():
                self.get_logger().info(f"UDP preview enabled -> udp://{self.runtime_config.laptop_ip}:{UDP_PORT}")
            else:
                self.get_logger().warning("UDP preview requested but writer could not open")
                self.udp_writer.release()
                self.udp_writer = None

        self.timer = self.create_timer(1.0 / self.runtime_config.camera_fps, self._tick)
        self.get_logger().info(
            f"{self.detector.backend_name} tracker on {self.camera_device} @ {self.frame_w}x{self.frame_h}, "
            f"fps={self.runtime_config.camera_fps}, model={model_path}, providers={self.detector.providers}, publishing /pixel_error"
        )

    def _declare_runtime_parameters(self) -> None:
        defaults = build_runtime_config(_WORKSPACE_ROOT, USE_SIM, IS_MAC)
        self.declare_parameter("platform_profile", defaults.platform_profile)
        self.declare_parameter("camera_device_candidates", list(defaults.camera_device_candidates))
        self.declare_parameter("camera_width", defaults.camera_width)
        self.declare_parameter("camera_height", defaults.camera_height)
        self.declare_parameter("camera_fps", defaults.camera_fps)
        self.declare_parameter("sim_camera_index", defaults.sim_camera_index)
        self.declare_parameter("enable_udp_preview", defaults.enable_udp_preview)
        self.declare_parameter("enable_imshow", defaults.enable_imshow)
        self.declare_parameter("model_path_sim", str(defaults.model_path_sim))
        self.declare_parameter("model_path_real", str(defaults.model_path_real))

    def _runtime_parameters(self) -> Dict[str, object]:
        names = (
            "platform_profile",
            "camera_device_candidates",
            "camera_width",
            "camera_height",
            "camera_fps",
            "sim_camera_index",
            "enable_udp_preview",
            "enable_imshow",
            "model_path_sim",
            "model_path_real",
        )
        return {name: self.get_parameter(name).value for name in names}

    def _publish_box_error(self, best_box: DetectionBox) -> None:
        self.msg.x, self.msg.y = compute_pixel_error(best_box, self.frame_w, self.frame_h)
        self.publisher_.publish(self.msg)

    def _tick(self) -> None:
        ok, frame = self.cap.read()
        if not ok:
            return
        best_box = self.detector.detect_best_box(frame)
        if best_box is not None:
            self._publish_box_error(best_box)
            x1, y1, x2, y2 = map(int, [best_box.x1, best_box.y1, best_box.x2, best_box.y2])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        if self.runtime_config.enable_imshow:
            cv2.imshow("YOLO Tracker", frame)
        if self.udp_writer is not None:
            self.udp_writer.write(frame)
        if self.runtime_config.enable_imshow and cv2.waitKey(1) & 0xFF == ord("q"):
            request_shutdown()

    def destroy_node(self):
        try:
            close_detector = getattr(self.detector, "close", None)
            if close_detector is not None:
                close_detector()
        except Exception:
            pass
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
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TrackerNode()
        rclpy.spin(node)
    except SHUTDOWN_EXCEPTIONS:
        pass
    finally:
        shutdown_node(node)
