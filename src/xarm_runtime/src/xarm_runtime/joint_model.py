import math
from typing import Mapping


THETA_FULL_RANGE_RAD = 2.0 * math.pi / 3.0  # ±2π/3 from center

JOINT_ORDER = ("base", "shoulder", "elbow", "camera")

JOINT_LIMITS = {
    "base": (-THETA_FULL_RANGE_RAD, THETA_FULL_RANGE_RAD),
    "shoulder": (-1.57, 1.57),
    "elbow": (-1.57, THETA_FULL_RANGE_RAD),
    "camera": (-THETA_FULL_RANGE_RAD, THETA_FULL_RANGE_RAD),
}

JOINTS = {
    "base": {
        "servo_id": 6,
        "topic": "/xarm/xarm_6_joint/cmd_pos",
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": JOINT_LIMITS["base"][0],
        "max_rad": JOINT_LIMITS["base"][1],
    },
    "shoulder": {
        "servo_id": 5,
        "topic": "/xarm/xarm_5_joint/cmd_pos",
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": JOINT_LIMITS["shoulder"][0],
        "max_rad": JOINT_LIMITS["shoulder"][1],
    },
    "elbow": {
        "servo_id": 4,
        "topic": "/xarm/xarm_4_joint/cmd_pos",
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": JOINT_LIMITS["elbow"][0],
        "max_rad": JOINT_LIMITS["elbow"][1],
    },
    "camera": {
        "servo_id": 3,
        "topic": "/xarm/xarm_3_joint/cmd_pos",
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": JOINT_LIMITS["camera"][0],
        "max_rad": JOINT_LIMITS["camera"][1],
    },
}

MIN_WRITE_PERIOD_SEC = 0.03
MIN_DELTA_COUNTS = 4


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def position_to_radians(position: float) -> float:
    return (position - 500.0) * math.pi / 750.0


def radians_to_position(theta: float) -> int:
    return round(500.0 + theta * 750.0 / math.pi)


def apply_joint_calibration(angle_rad: float, cfg: Mapping[str, float]) -> float:
    return cfg["direction"] * (angle_rad - cfg["offset_rad"])


def joint_angle_to_counts(angle_rad: float, cfg: Mapping[str, float]) -> int:
    calibrated = apply_joint_calibration(angle_rad, cfg)
    return int(clamp(radians_to_position(calibrated), 0, 1000))
