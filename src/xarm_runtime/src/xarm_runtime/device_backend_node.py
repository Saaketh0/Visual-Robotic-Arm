try:
    import serial
except ImportError:  # pragma: no cover - import guard for non-hardware test envs
    serial = None

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

from xarm_runtime.backends.serial_device import compute_servo_writes, move_servo_packet
from xarm_runtime.joint_model import JOINT_ORDER, MIN_WRITE_PERIOD_SEC
from xarm_runtime.ros_runtime import SHUTDOWN_EXCEPTIONS, shutdown_node


class DeviceBackendNode(Node):
    def __init__(self) -> None:
        super().__init__("device_command_node")
        if serial is None:
            raise RuntimeError("pyserial is required for device_backend_node runtime use.")
        self.declare_parameter("serial_port", "/dev/ttyTHS1")
        self.declare_parameter("baudrate", 9600)
        self.declare_parameter("move_time_ms", 80)

        port = self.get_parameter("serial_port").get_parameter_value().string_value
        baud = self.get_parameter("baudrate").get_parameter_value().integer_value
        self._move_time_ms = self.get_parameter("move_time_ms").get_parameter_value().integer_value
        self.last_counts = {name: None for name in JOINT_ORDER}
        self.last_write_time = self.get_clock().now()
        self.sub = self.create_subscription(Float64MultiArray, "joint_cmds", self._on_cmds, 10)
        try:
            self._ser = serial.Serial(port, baud, timeout=1)
        except Exception as exc:
            raise RuntimeError(
                f"Could not open serial port {port} at {baud}. "
                "Check the configured serial_port in jetson.yaml, device permissions, and cable power."
            ) from exc
        self.get_logger().info(
            "device_command_node on /joint_cmds; joints: " + ", ".join(JOINT_ORDER) + f"; serial={port} @ {baud}"
        )

    def _on_cmds(self, msg: Float64MultiArray) -> None:
        if len(msg.data) < len(JOINT_ORDER):
            self.get_logger().warning(
                f"/joint_cmds has {len(msg.data)} values, expected {len(JOINT_ORDER)} ({JOINT_ORDER}); dropping"
            )
            return
        now = self.get_clock().now()
        elapsed = (now - self.last_write_time).nanoseconds / 1e9
        if elapsed < MIN_WRITE_PERIOD_SEC:
            return
        wrote_any = False
        for name, servo_id, counts in compute_servo_writes(msg.data, self.last_counts):
            self._write_servo(servo_id, counts)
            self.last_counts[name] = counts
            wrote_any = True
        if wrote_any:
            self.last_write_time = now

    def _write_servo(self, servo_id: int, counts: int) -> None:
        packet = move_servo_packet(servo_id, counts, self._move_time_ms)
        self._ser.write(packet)
        self._ser.flush()
        self.get_logger().debug(f"servo {servo_id} -> {counts}")

    def destroy_node(self) -> bool:
        self._ser.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = DeviceBackendNode()
        rclpy.spin(node)
    except SHUTDOWN_EXCEPTIONS:
        pass
    finally:
        shutdown_node(node)
