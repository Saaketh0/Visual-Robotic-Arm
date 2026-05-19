from typing import Optional

import rclpy
from rclpy.node import Node

try:
    from rclpy.executors import ExternalShutdownException
except Exception:  # pragma: no cover - rclpy version compatibility
    ExternalShutdownException = RuntimeError

SHUTDOWN_EXCEPTIONS = (KeyboardInterrupt, ExternalShutdownException)


def request_shutdown() -> None:
    try:
        if rclpy.ok():
            rclpy.shutdown()
    except Exception:
        pass


def shutdown_node(node: Optional[Node]) -> None:
    if node is not None:
        try:
            node.destroy_node()
        except Exception:
            pass
    request_shutdown()
