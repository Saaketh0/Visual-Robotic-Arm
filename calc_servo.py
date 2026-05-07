#!/usr/bin/env python3
"""
Visual-servo controller.

In : /pixel_error  (geometry_msgs/Point)  -- center-relative pixel error
Out: /joint_cmds   (std_msgs/Float64MultiArray)
       data = [base_rad, shoulder_rad, elbow_rad, camera_rad] (fixed order)

Stays backend-agnostic: a Gazebo bridge node OR a real-robot driver node
subscribes to /joint_cmds.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import Float64MultiArray
from joint_model import JOINT_LIMITS, JOINT_ORDER, clamp

# Image geometry used for center / normalization (must match camera frame)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

CX = FRAME_WIDTH / 2.0
CY = FRAME_HEIGHT / 2.0

INITIAL_JOINT_ANGLES = {
    "base": 0.0,
    "shoulder": -0.8378,
    "elbow": 1.5700,
    "camera": 0.8378,
}

# Tune these
GAIN_X = 0.5
GAIN_Y = 0.1

# Temporary experiment:
# - x error moves the base strongly
# - y error is mostly handled by the wrist/camera joint
# - shoulder and elbow contribute lightly so the arm can share the load
TEMP_BASE_WRIST_ONLY_MODE = False

# Flip signs if movement is backwards. X is already correct; y should move
# coherently across the shoulder/elbow/camera chain in Gazebo.
BASE_DIRECTION = 1.0
SHOULDER_DIRECTION = 1.25
ELBOW_DIRECTION = 1.35
CAMERA_DIRECTION = 1.55

# Ignore tiny errors near the center
DEADBAND_X = 50
DEADBAND_Y = 50

# Integration timing guards (seconds)
DEFAULT_DT = 1.0 / 30.0
MIN_DT = 1e-4
MAX_DT = 0.2

# Posture/stability bias:
# Keep the arm in a lower, less extended pose while still tracking.
POSTURE_TARGET = {
    "shoulder": -0.8378,
    "elbow": 1.5700,
}
POSTURE_PULL_GAIN = {
    "shoulder": 0.01,
    "elbow": 0.01,
}

# Cap joint motion per second to reduce wobble/jitter.
MAX_RATE_RAD_S = {
    "base": 0.75,
    "shoulder": 0.3,
    "elbow": 0.4,
    "camera": 0.5,
}

# Smooth the published joint setpoints so the backend sees fewer tiny reversals.
OUTPUT_FILTER_ALPHA = 0.20


class ServoCalcNode(Node):
    def __init__(self):
        super().__init__("servo_calc_node")

        self.joint_angles = dict(INITIAL_JOINT_ANGLES)
        if TEMP_BASE_WRIST_ONLY_MODE:
            self.joint_angles["shoulder"] = POSTURE_TARGET["shoulder"]
            self.joint_angles["elbow"] = POSTURE_TARGET["elbow"]
        self._published_joint_angles = dict(INITIAL_JOINT_ANGLES)
        if TEMP_BASE_WRIST_ONLY_MODE:
            self._published_joint_angles["shoulder"] = POSTURE_TARGET["shoulder"]
            self._published_joint_angles["elbow"] = POSTURE_TARGET["elbow"]
        self._last_t = self.get_clock().now()

        self.subscriber = self.create_subscription(
            Point, "pixel_error", self.update_controller, 10
        )
        self.publisher_ = self.create_publisher(
            Float64MultiArray, "joint_cmds", 10
        )

        self.get_logger().info(
            "servo_calc_node listening on /pixel_error, "
            f"publishing /joint_cmds [{', '.join(JOINT_ORDER)}]"
        )
        self.send_all_joints()

    def _clamp_delta_rate(self, name: str, delta: float, dt: float) -> float:
        max_step = MAX_RATE_RAD_S[name] * dt
        return clamp(delta, -max_step, max_step)

    def send_all_joints(self):
        self._published_joint_angles = {
            name: self._published_joint_angles[name]
            + OUTPUT_FILTER_ALPHA * (self.joint_angles[name] - self._published_joint_angles[name])
            for name in JOINT_ORDER
        }
        msg = Float64MultiArray()
        msg.data = [float(self._published_joint_angles[name]) for name in JOINT_ORDER]
        self.publisher_.publish(msg)

    def update_controller(self, error: Point):
        now = self.get_clock().now()
        dt = (now - self._last_t).nanoseconds / 1e9
        self._last_t = now
        if dt <= 0.0:
            dt = DEFAULT_DT
        dt = clamp(dt, MIN_DT, MAX_DT)

        error_x_pixels = error.x
        error_y_pixels = error.y

        if abs(error_x_pixels) < DEADBAND_X:
            error_x_pixels = 0.0
        if abs(error_y_pixels) < DEADBAND_Y:
            error_y_pixels = 0.0

        # Normalize errors to roughly -1 to 1
        error_x = error_x_pixels / CX
        error_y = error_y_pixels / CY

        # dt-scaled integration keeps behavior stable when callback rate varies.
        d_base = BASE_DIRECTION * GAIN_X * error_x * dt
        d_shoulder = SHOULDER_DIRECTION * GAIN_Y * error_y * dt
        d_elbow = ELBOW_DIRECTION * GAIN_Y * error_y * dt
        d_camera = CAMERA_DIRECTION * GAIN_Y * error_y * dt

        tracking_deltas = {
            "base": d_base,
            "shoulder": d_shoulder,
            "elbow": d_elbow,
            "camera": d_camera,
        }

        # Pull toward a lower/more stable posture while tracking.
        posture_deltas = {
            "base": 0.0,
            "shoulder": POSTURE_PULL_GAIN["shoulder"]
            * (POSTURE_TARGET["shoulder"] - self.joint_angles["shoulder"]) * dt,
            "elbow": POSTURE_PULL_GAIN["elbow"]
            * (POSTURE_TARGET["elbow"] - self.joint_angles["elbow"]) * dt,
            "camera": 0.0,
        }

        deltas = {
            name: self._clamp_delta_rate(
                name,
                tracking_deltas[name] + posture_deltas[name],
                dt,
            )
            for name in JOINT_ORDER
        }

        # Anti-windup: don't integrate further into a hard limit.
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

        self.send_all_joints()


def main(args=None):
    rclpy.init(args=args)
    node = ServoCalcNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
