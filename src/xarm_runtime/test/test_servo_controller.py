import math

from xarm_runtime.servo_controller_node import MAX_DT, MAX_RATE_RAD_S, ServoController


def test_deadband_suppresses_small_errors() -> None:
    controller = ServoController()
    before = dict(controller.joint_angles)
    controller.step(10.0, 10.0, 0.05)
    assert controller.joint_angles == before


def test_large_x_error_moves_base_positive() -> None:
    controller = ServoController()
    values = controller.step(320.0, 0.0, 0.1)
    assert controller.joint_angles["base"] > 0.0
    assert values[0] > 0.0


def test_y_error_uses_only_camera_not_shoulder_or_elbow() -> None:
    controller = ServoController()
    before_shoulder = controller.joint_angles["shoulder"]
    before_elbow = controller.joint_angles["elbow"]
    before_camera = controller.joint_angles["camera"]
    controller.step(0.0, 240.0, 0.1)
    assert controller.joint_angles["shoulder"] == before_shoulder
    assert controller.joint_angles["elbow"] == before_elbow
    assert controller.joint_angles["camera"] > before_camera


def test_opposite_y_errors_move_camera_in_opposite_directions() -> None:
    positive_y = ServoController()
    negative_y = ServoController()
    initial_camera = positive_y.joint_angles["camera"]

    positive_y.step(0.0, 240.0, 0.1)
    negative_y.step(0.0, -240.0, 0.1)

    assert positive_y.joint_angles["camera"] > initial_camera
    assert negative_y.joint_angles["camera"] < initial_camera


def test_dt_is_clamped_to_max_for_stability() -> None:
    controller = ServoController()
    controller.step(320.0, 240.0, 10.0)
    assert controller.joint_angles["base"] <= MAX_RATE_RAD_S["base"] * MAX_DT + 1e-9


def test_joint_limits_prevent_further_windup() -> None:
    controller = ServoController(joint_angles={"base": 10.0, "shoulder": -0.8378, "elbow": 1.57, "camera": 0.8378}, published_joint_angles={"base": 10.0, "shoulder": -0.8378, "elbow": 1.57, "camera": 0.8378})
    controller.step(320.0, 0.0, 0.1)
    assert math.isfinite(controller.joint_angles["base"])
    assert controller.joint_angles["base"] <= 2.0943951023931953
