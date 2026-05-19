import math

from xarm_runtime.joint_model import (
    JOINT_ORDER,
    JOINTS,
    apply_joint_calibration,
    clamp,
    joint_angle_to_counts,
    position_to_radians,
    radians_to_position,
)


def test_clamp_binds_values() -> None:
    assert clamp(-2.0, -1.0, 1.0) == -1.0
    assert clamp(0.5, -1.0, 1.0) == 0.5
    assert clamp(2.0, -1.0, 1.0) == 1.0


def test_position_round_trip_is_stable() -> None:
    theta = position_to_radians(650)
    assert radians_to_position(theta) == 650


def test_apply_joint_calibration_respects_direction_and_offset() -> None:
    cfg = {"direction": -1, "offset_rad": 0.2}
    assert math.isclose(apply_joint_calibration(0.5, cfg), -0.3)


def test_joint_angle_to_counts_clamps_output() -> None:
    assert joint_angle_to_counts(99.0, JOINTS["base"]) == 1000
    assert joint_angle_to_counts(-99.0, JOINTS["base"]) == 0


def test_joint_order_has_expected_topics() -> None:
    assert JOINT_ORDER == ("base", "shoulder", "elbow", "camera")
    assert JOINTS["camera"]["topic"].endswith("xarm_3_joint/cmd_pos")
