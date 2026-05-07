#!/usr/bin/env python3
"""
Gazebo command backend (Option A: explicit Homebrew `gz`).

This node is intentionally a pure forwarder:
- it receives `/joint_cmds`
- validates the message length
- streams each joint value to the matching Gazebo topic unchanged

All motion math, clamping, and sign handling stay in `calc_servo.py`.
"""

from __future__ import annotations

import subprocess
from typing import Callable, Iterable, Tuple

try:  # pragma: no cover - runtime path only
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float64MultiArray
except ImportError:  # pragma: no cover - allows unit tests without ROS deps
    rclpy = None
    Node = object  # type: ignore[assignment]
    Float64MultiArray = None  # type: ignore[assignment]

from joint_model import JOINT_ORDER, JOINTS

GZ_BIN = "/opt/homebrew/bin/gz"

TopicSender = Callable[[str, float], None]


def _topic_pairs() -> Tuple[Tuple[str, str], ...]:
    return tuple((name, JOINTS[name]["topic"]) for name in JOINT_ORDER)


def _send_gz_double(topic: str, value: float) -> None:
    subprocess.run(
        [
            GZ_BIN,
            "topic",
            "-t",
            topic,
            "-m",
            "gz.msgs.Double",
            "-p",
            f"data: {float(value)}",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def forward_joint_cmds(
    values: Iterable[float],
    topic_sender: TopicSender = _send_gz_double,
) -> None:
    for (name, topic), value in zip(_topic_pairs(), values):
        topic_sender(topic, float(value))


class GazeboCommandNode(Node):  # pragma: no cover - runtime path only
    def __init__(self):
        super().__init__("gazebo_command_node")

        self.sub = self.create_subscription(
            Float64MultiArray, "joint_cmds", self._on_cmds, 10
        )

        self.get_logger().info(
            "gazebo_command_node forwarding /joint_cmds via "
            f"{GZ_BIN} -> " + ", ".join(topic for _, topic in _topic_pairs())
        )

    def _on_cmds(self, msg: Float64MultiArray):
        if len(msg.data) < len(JOINT_ORDER):
            self.get_logger().warning(
                f"/joint_cmds has {len(msg.data)} values, expected "
                f"{len(JOINT_ORDER)} ({JOINT_ORDER}); dropping"
            )
            return

        forward_joint_cmds(msg.data)


def main(args=None):  # pragma: no cover - runtime path only
    if rclpy is None:
        raise RuntimeError("ROS 2 Python dependencies are unavailable.")

    rclpy.init(args=args)
    node = GazeboCommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
