from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

from xarm_gazebo_sim.backends.gazebo import GZ_BIN, forward_joint_cmds, topic_pairs
from xarm_runtime.joint_model import JOINT_ORDER


class GazeboBackendNode(Node):
    def __init__(self) -> None:
        super().__init__("gazebo_command_node")
        self.sub = self.create_subscription(Float64MultiArray, "joint_cmds", self._on_cmds, 10)
        self.get_logger().info(
            "gazebo_command_node forwarding /joint_cmds via "
            f"{GZ_BIN} -> " + ", ".join(topic for _, topic in topic_pairs())
        )

    def _on_cmds(self, msg: Float64MultiArray) -> None:
        if len(msg.data) < len(JOINT_ORDER):
            self.get_logger().warning(
                f"/joint_cmds has {len(msg.data)} values, expected {len(JOINT_ORDER)} ({JOINT_ORDER}); dropping"
            )
            return
        forward_joint_cmds(msg.data)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GazeboBackendNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
