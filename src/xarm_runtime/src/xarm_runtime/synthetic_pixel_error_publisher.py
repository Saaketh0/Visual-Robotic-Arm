#!/usr/bin/env python3
"""ROS2 node that publishes a deterministic synthetic `pixel_error` path.

This node is intended for tuning `calc_servo.py` without running the camera-based
tracker. It publishes the same contract as the real tracker:

- topic:  `pixel_error` (i.e. /pixel_error)
- type:   geometry_msgs/Point
- fields: x/y as pixel offsets, z=0
"""

import math
from dataclasses import dataclass
from typing import List, Tuple

import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node

from xarm_runtime.ros_runtime import SHUTDOWN_EXCEPTIONS, request_shutdown, shutdown_node


Point2D = Tuple[float, float]

POINT_REPEAT_FACTOR = 15


@dataclass(frozen=True)
class PathConfig:
    max_x: float
    max_y: float
    step_px: float
    publish_rate_hz: float
    corner_dwell_sec: float
    spiral_turns: int
    spiral_inward_step: float
    loop: bool


def _point(x: float, y: float) -> Point2D:
    return (float(x), float(y))


def _segment_sample_count(start: Point2D, end: Point2D, step_px: float) -> int:
    distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    return max(1, int(math.ceil(distance / step_px)))


def line_segment(start: Point2D, end: Point2D, step_px: float) -> List[Point2D]:
    steps = _segment_sample_count(start, end, step_px)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return [
        _point(start[0] + (dx * i) / steps, start[1] + (dy * i) / steps)
        for i in range(1, steps + 1)
    ]


def repeat_point(point: Point2D, count: int) -> List[Point2D]:
    return [point for _ in range(max(0, count))]


def stretch_path(path: List[Point2D], repeat_factor: int) -> List[Point2D]:
    if repeat_factor <= 1:
        return path
    stretched: List[Point2D] = []
    for point in path:
        stretched.extend(repeat_point(point, repeat_factor))
    return stretched


def _append_segment(path: List[Point2D], current: Point2D, target: Point2D, step_px: float) -> Point2D:
    path.extend(line_segment(current, target, step_px))
    return target


def spiral_inward_path(start: Point2D, config: PathConfig) -> List[Point2D]:
    path: List[Point2D] = []
    current = start

    left = -config.max_x
    right = config.max_x
    bottom = -config.max_y
    top = config.max_y

    for _ in range(max(0, config.spiral_turns)):
        current = _append_segment(path, current, _point(right, bottom), config.step_px)
        bottom += config.spiral_inward_step

        current = _append_segment(path, current, _point(right, top), config.step_px)
        right -= config.spiral_inward_step

        current = _append_segment(path, current, _point(left, top), config.step_px)
        top -= config.spiral_inward_step

        current = _append_segment(path, current, _point(left, bottom), config.step_px)
        left += config.spiral_inward_step

        if left >= right or bottom >= top:
            break

    if current[0] != 0.0:
        current = _append_segment(path, current, _point(0.0, current[1]), config.step_px)
    if current[1] != 0.0:
        current = _append_segment(path, current, _point(0.0, 0.0), config.step_px)
    return path


def assemble_path(config: PathConfig) -> List[Point2D]:
    path: List[Point2D] = [_point(0.0, 0.0)]
    dwell_points = int(round(config.corner_dwell_sec * config.publish_rate_hz))

    current = _point(0.0, 0.0)
    corners = [
        _point(-config.max_x, 0.0),
        _point(-config.max_x, config.max_y),
        _point(config.max_x, config.max_y),
        _point(config.max_x, -config.max_y),
        _point(-config.max_x, -config.max_y),
    ]

    for corner in corners:
        current = _append_segment(path, current, corner, config.step_px)
        path.extend(repeat_point(corner, dwell_points))

    path.extend(spiral_inward_path(current, config))
    return stretch_path(path, POINT_REPEAT_FACTOR)


class SyntheticPixelErrorPublisher(Node):
    def __init__(self):
        super().__init__("synthetic_pixel_error_publisher")

        self.declare_parameter("max_x", 160.0)
        self.declare_parameter("max_y", 120.0)
        self.declare_parameter("step_px", 20.0)
        self.declare_parameter("publish_rate_hz", 20.0)
        self.declare_parameter("corner_dwell_sec", 0.2)
        self.declare_parameter("spiral_turns", 4)
        self.declare_parameter("spiral_inward_step", 20.0)
        self.declare_parameter("loop", True)

        config = PathConfig(
            max_x=float(self.get_parameter("max_x").value),
            max_y=float(self.get_parameter("max_y").value),
            step_px=float(self.get_parameter("step_px").value),
            publish_rate_hz=float(self.get_parameter("publish_rate_hz").value),
            corner_dwell_sec=float(self.get_parameter("corner_dwell_sec").value),
            spiral_turns=int(self.get_parameter("spiral_turns").value),
            spiral_inward_step=float(self.get_parameter("spiral_inward_step").value),
            loop=bool(self.get_parameter("loop").value),
        )

        self._config = config
        self._path = assemble_path(config)
        self._i = 0

        self._publisher = self.create_publisher(Point, "pixel_error", 10)
        self._timer = self.create_timer(1.0 / config.publish_rate_hz, self._tick)

        self.get_logger().info(
            "Synthetic pixel_error publisher started "
            f"({len(self._path)} points, loop={'yes' if config.loop else 'no'})"
        )

    def _tick(self) -> None:
        if self._i >= len(self._path):
            if self._config.loop:
                self._i = 0
            else:
                self.get_logger().info("Synthetic path complete; shutting down.")
                request_shutdown()
                return

        x, y = self._path[self._i]
        msg = Point()
        msg.x = float(x)
        msg.y = float(y)
        msg.z = 0.0
        self._publisher.publish(msg)
        self._i += 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SyntheticPixelErrorPublisher()
        rclpy.spin(node)
    except SHUTDOWN_EXCEPTIONS:
        pass
    finally:
        shutdown_node(node)
