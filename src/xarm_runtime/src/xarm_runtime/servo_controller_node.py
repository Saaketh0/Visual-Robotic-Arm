from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

from xarm_runtime.joint_model import JOINT_LIMITS, JOINT_ORDER, clamp
from xarm_runtime.ros_runtime import SHUTDOWN_EXCEPTIONS, shutdown_node

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CX = FRAME_WIDTH / 2.0
CY = FRAME_HEIGHT / 2.0

ELBOW_START_ANGLE = 0.8

INITIAL_JOINT_ANGLES = {
    "base": 0.0,
    "shoulder": 0.8378,
    "elbow": ELBOW_START_ANGLE,
    "camera": -1.2,
}
GAIN_X = 0.8
GAIN_Y = 0.25
BASE_DIRECTION = 1.0
CAMERA_DIRECTION = 1.55
DEADBAND_X = 50
DEADBAND_Y = 50
DEFAULT_DT = 1.0 / 50.0
MIN_DT = 1e-4
MAX_DT = 0.2
MAX_RATE_RAD_S = {"base": 1.2, "shoulder": 0.3, "elbow": 0.4, "camera": 1.2}
OUTPUT_FILTER_ALPHA = 0.35


@dataclass
class ServoController:
    joint_angles: Dict[str, float] = field(default_factory=lambda: dict(INITIAL_JOINT_ANGLES))
    published_joint_angles: Dict[str, float] = field(default_factory=lambda: dict(INITIAL_JOINT_ANGLES))

    def _clamp_delta_rate(self, name: str, delta: float, dt: float) -> float:
        max_step = MAX_RATE_RAD_S[name] * dt
        return clamp(delta, -max_step, max_step)

    def _normalize_error(self, error_x_pixels: float, error_y_pixels: float) -> Tuple[float, float]:
        if abs(error_x_pixels) < DEADBAND_X:
            error_x_pixels = 0.0
        if abs(error_y_pixels) < DEADBAND_Y:
            error_y_pixels = 0.0
        return error_x_pixels / CX, error_y_pixels / CY

    def current_output(self) -> List[float]:
        return [float(self.published_joint_angles[name]) for name in JOINT_ORDER]

    def step(self, error_x_pixels: float, error_y_pixels: float, dt: float) -> List[float]:
        dt = clamp(dt if dt > 0.0 else DEFAULT_DT, MIN_DT, MAX_DT)
        error_x, error_y = self._normalize_error(error_x_pixels, error_y_pixels)

        deltas = {
            "base": self._clamp_delta_rate("base", BASE_DIRECTION * GAIN_X * error_x * dt, dt),
            "shoulder": 0.0,
            "elbow": 0.0,
            "camera": self._clamp_delta_rate("camera", CAMERA_DIRECTION * GAIN_Y * error_y * dt, dt),
        }
        for name, delta in deltas.items():
            low, high = JOINT_LIMITS[name]
            current = self.joint_angles[name]
            at_low_and_pushing_lower = current <= low and delta < 0.0
            at_high_and_pushing_higher = current >= high and delta > 0.0
            if at_low_and_pushing_lower or at_high_and_pushing_higher:
                continue
            self.joint_angles[name] = current + delta
        for name, angle in self.joint_angles.items():
            low, high = JOINT_LIMITS[name]
            self.joint_angles[name] = clamp(angle, low, high)

        self.published_joint_angles = {
            name: self.published_joint_angles[name]
            + OUTPUT_FILTER_ALPHA * (self.joint_angles[name] - self.published_joint_angles[name])
            for name in JOINT_ORDER
        }
        return self.current_output()


class ServoControllerNode(Node):
    def __init__(self) -> None:
        super().__init__("servo_calc_node")
        self._controller = ServoController()
        self._last_t = self.get_clock().now()
        self.subscriber = self.create_subscription(Point, "pixel_error", self.update_controller, 10)
        self.publisher_ = self.create_publisher(Float64MultiArray, "joint_cmds", 10)
        self.get_logger().info(
            "servo_calc_node listening on /pixel_error, "
            f"publishing /joint_cmds [{', '.join(JOINT_ORDER)}]"
        )
        self.send_joint_values(self._controller.current_output())

    def send_joint_values(self, values: List[float]) -> None:
        msg = Float64MultiArray()
        msg.data = [float(value) for value in values]
        self.publisher_.publish(msg)

    def update_controller(self, error: Point) -> None:
        now = self.get_clock().now()
        dt = (now - self._last_t).nanoseconds / 1e9
        self._last_t = now
        values = self._controller.step(error.x, error.y, dt)
        self.send_joint_values(values)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = ServoControllerNode()
        rclpy.spin(node)
    except SHUTDOWN_EXCEPTIONS:
        pass
    finally:
        shutdown_node(node)
