import serial

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from joint_model import (
    JOINTS,
    JOINT_ORDER,
    MIN_DELTA_COUNTS,
    MIN_WRITE_PERIOD_SEC,
    clamp,
    joint_angle_to_counts,
)


def move_servo_packet(servo_id: int, position: int, move_time_ms: int) -> bytearray:
    """Hiwonder packet: 55 55 LEN CMD NUM_SERVOS TIME_L TIME_H SERVO_ID POS_L POS_H"""
    position = int(max(0, min(1000, position)))
    move_time_ms = int(max(0, min(30000, move_time_ms)))

    return bytearray(
        [
            0x55,
            0x55,
            0x08,
            0x03,  # CMD_SERVO_MOVE
            0x01,
            move_time_ms & 0xFF,
            (move_time_ms >> 8) & 0xFF,
            servo_id,
            position & 0xFF,
            (position >> 8) & 0xFF,
        ]
    )


class DeviceCommandNode(Node):
    def __init__(self):
        super().__init__("device_command_node")

        self.declare_parameter("serial_port", "/dev/ttyTHS1")
        self.declare_parameter("baudrate", 9600)
        self.declare_parameter("move_time_ms", 80)

        port = self.get_parameter("serial_port").get_parameter_value().string_value
        baud = self.get_parameter("baudrate").get_parameter_value().integer_value
        self._move_time_ms = self.get_parameter("move_time_ms").get_parameter_value().integer_value

        self.last_counts = {name: None for name in JOINT_ORDER}
        self.last_write_time = self.get_clock().now()

        self.sub = self.create_subscription(
            Float64MultiArray, "joint_cmds", self._on_cmds, 10
        )

        self._ser = serial.Serial(port, baud, timeout=1)

        self.get_logger().info(
            "device_command_node on /joint_cmds; joints: "
            + ", ".join(JOINT_ORDER)
            + f"; serial={port} @ {baud}"
        )

    def _on_cmds(self, msg: Float64MultiArray):
        if len(msg.data) < len(JOINT_ORDER):
            self.get_logger().warning(
                f"/joint_cmds has {len(msg.data)} values, expected "
                f"{len(JOINT_ORDER)} ({JOINT_ORDER}); dropping"
            )
            return

        now = self.get_clock().now()
        elapsed = (now - self.last_write_time).nanoseconds / 1e9
        if elapsed < MIN_WRITE_PERIOD_SEC:
            return

        wrote_any = False
        for name, angle in zip(JOINT_ORDER, msg.data):
            cfg = JOINTS[name]

            angle = clamp(float(angle), cfg["min_rad"], cfg["max_rad"])
            counts = joint_angle_to_counts(angle, cfg)

            prev = self.last_counts[name]
            if prev is not None and abs(counts - prev) < MIN_DELTA_COUNTS:
                continue

            self._write_servo(cfg["servo_id"], counts)
            self.last_counts[name] = counts
            wrote_any = True

        if wrote_any:
            self.last_write_time = now

    def _write_servo(self, servo_id: int, counts: int):
        packet = move_servo_packet(servo_id, counts, self._move_time_ms)
        self._ser.write(packet)
        self._ser.flush()
        self.get_logger().debug(f"servo {servo_id} -> {counts}")

    def destroy_node(self):
        self._ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DeviceCommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
