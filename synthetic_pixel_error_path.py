#!/usr/bin/env python3
"""Standalone synthetic /pixel_error publisher for arm tuning.

This utility is intentionally detachable:
- no launch-file wiring
- no import from production nodes
- easy to delete as a single file later

The generated path starts at the origin, traces an outer square, then
contracts inward with a rectangular spiral until it returns to the origin.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

try:  # pragma: no cover - exercised in ROS runtime, not in unit tests
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Point
except ImportError:  # pragma: no cover - allows path tests without ROS deps
    rclpy = None
    Node = object  # type: ignore[assignment]
    Point = None  # type: ignore[assignment]


Point2D = Tuple[float, float]

POINT_REPEAT_FACTOR = 15


@dataclass(frozen=True)
class PathConfig:
    max_x: float = 160.0
    max_y: float = 120.0
    step_px: float = 20.0
    publish_rate_hz: float = 20.0
    corner_dwell_sec: float = 0.2
    spiral_turns: int = 4
    spiral_inward_step: float = 20.0
    loop: bool = True


def _validate_config(config: PathConfig) -> None:
    if config.max_x <= 0 or config.max_y <= 0:
        raise ValueError("max_x and max_y must be positive")
    if config.step_px <= 0:
        raise ValueError("step_px must be positive")
    if config.publish_rate_hz <= 0:
        raise ValueError("publish_rate_hz must be positive")
    if config.corner_dwell_sec < 0:
        raise ValueError("corner_dwell_sec cannot be negative")
    if config.spiral_turns < 0:
        raise ValueError("spiral_turns cannot be negative")
    if config.spiral_inward_step <= 0:
        raise ValueError("spiral_inward_step must be positive")


def _point(x: float, y: float) -> Point2D:
    return (float(x), float(y))


def _segment_sample_count(start: Point2D, end: Point2D, step_px: float) -> int:
    distance = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    return max(1, int(math.ceil(distance / step_px)))


def line_segment(start: Point2D, end: Point2D, step_px: float) -> List[Point2D]:
    """Return end-inclusive points between two axis-aligned or diagonal points."""
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


def _append_corner_dwell(path: List[Point2D], corner: Point2D, dwell_points: int) -> None:
    path.extend(repeat_point(corner, dwell_points))


def spiral_inward_path(
    start: Point2D,
    config: PathConfig,
) -> List[Point2D]:
    """Generate the inward rectangular spiral from the bottom-left corner."""
    _validate_config(config)

    path: List[Point2D] = []
    current = start

    left = -config.max_x
    right = config.max_x
    bottom = -config.max_y
    top = config.max_y

    for _ in range(config.spiral_turns):
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
    """Assemble the full synthetic path in the requested leg order."""
    _validate_config(config)

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
        _append_corner_dwell(path, corner, dwell_points)

    path.extend(spiral_inward_path(current, config))
    return stretch_path(path, POINT_REPEAT_FACTOR)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a deterministic synthetic /pixel_error path.",
    )
    parser.add_argument("--max-x", type=float, default=PathConfig.max_x)
    parser.add_argument("--max-y", type=float, default=PathConfig.max_y)
    parser.add_argument("--step-px", type=float, default=PathConfig.step_px)
    parser.add_argument("--publish-rate-hz", type=float, default=PathConfig.publish_rate_hz)
    parser.add_argument("--corner-dwell-sec", type=float, default=PathConfig.corner_dwell_sec)
    parser.add_argument("--spiral-turns", type=int, default=PathConfig.spiral_turns)
    parser.add_argument(
        "--spiral-inward-step",
        type=float,
        default=PathConfig.spiral_inward_step,
    )
    parser.add_argument(
        "--loop",
        action=argparse.BooleanOptionalAction,
        default=PathConfig.loop,
        help="Repeat the generated path indefinitely (default: true).",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> PathConfig:
    return PathConfig(
        max_x=args.max_x,
        max_y=args.max_y,
        step_px=args.step_px,
        publish_rate_hz=args.publish_rate_hz,
        corner_dwell_sec=args.corner_dwell_sec,
        spiral_turns=args.spiral_turns,
        spiral_inward_step=args.spiral_inward_step,
        loop=args.loop,
    )


class SyntheticPixelErrorPublisher(Node):  # pragma: no cover - ROS runtime path
    def __init__(self, config: PathConfig):
        super().__init__("synthetic_pixel_error_publisher")
        if Point is None:
            raise RuntimeError("geometry_msgs.msg.Point is unavailable")

        self._config = config
        self._path = assemble_path(config)
        self._path_index = 0
        self._publisher = self.create_publisher(Point, "pixel_error", 10)
        self._timer = self.create_timer(1.0 / config.publish_rate_hz, self._tick)
        self.get_logger().info(
            "Publishing synthetic /pixel_error path "
            f"({len(self._path)} points, loop={'yes' if config.loop else 'no'})"
        )

    def _tick(self) -> None:
        if self._path_index >= len(self._path):
            if self._config.loop:
                self._path_index = 0
            else:
                self.get_logger().info("Synthetic /pixel_error path complete")
                rclpy.shutdown()
                return

        x, y = self._path[self._path_index]
        msg = Point()
        msg.x = float(x)
        msg.y = float(y)
        msg.z = 0.0
        self._publisher.publish(msg)
        self._path_index += 1


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - ROS runtime path
    parser = build_arg_parser()
    args, ros_args = parser.parse_known_args(argv)
    config = config_from_args(args)
    _validate_config(config)

    if rclpy is None or Point is None:
        raise RuntimeError(
            "ROS 2 Python dependencies are unavailable. "
            "Source the ROS environment before running this script."
        )

    rclpy.init(args=ros_args)
    node = SyntheticPixelErrorPublisher(config)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
