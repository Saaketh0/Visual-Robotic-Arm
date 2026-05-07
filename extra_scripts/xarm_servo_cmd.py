#!/usr/bin/env python3

import math
import subprocess
import sys

# Hiwonder/LewanSoul-style mapping:
# servo position 0-1000 maps to about 0-240 degrees.
# We treat 500 as the joint's neutral position.
RAD_PER_COUNT = (240.0 / 1000.0) * math.pi / 180.0

JOINTS = {
    "base": {
        "topic": "/xarm/xarm_6_joint/cmd_pos",
        "zero": 500,
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": -2.09,
        "max_rad": 2.09,
    },
    "shoulder": {
        "topic": "/xarm/xarm_5_joint/cmd_pos",
        "zero": 500,
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": -1.8,
        "max_rad": 1.8,
    },
    "elbow": {
        "topic": "/xarm/xarm_4_joint/cmd_pos",
        "zero": 500,
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": -1.8,
        "max_rad": 1.8,
    },
    "wrist_pitch": {
        "topic": "/xarm/xarm_3_joint/cmd_pos",
        "zero": 500,
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": -1.8,
        "max_rad": 1.8,
    },
    "wrist_roll": {
        "topic": "/xarm/xarm_2_joint/cmd_pos",
        "zero": 500,
        "direction": 1,
        "offset_rad": 0.0,
        "min_rad": -3.14,
        "max_rad": 3.14,
    },
}


def clamp(value, low, high):
    return max(low, min(high, value))


def servo_to_rad(position, zero, direction, offset_rad):
    return direction * (position - zero) * RAD_PER_COUNT + offset_rad


def send_gazebo_command(topic, angle_rad):
    subprocess.run(
        [
            "gz",
            "topic",
            "-t",
            topic,
            "-m",
            "gz.msgs.Double",
            "-p",
            f"data: {angle_rad}",
        ],
        check=True,
    )


def main():
    if len(sys.argv) != 3:
        print("Usage:")
        print("  python3 xarm_servo_cmd.py <joint> <servo_position>")
        print()
        print("Examples:")
        print("  python3 xarm_servo_cmd.py base 600")
        print("  python3 xarm_servo_cmd.py shoulder 450")
        print()
        print("Available joints:")
        for joint in JOINTS:
            print(f"  {joint}")
        sys.exit(1)

    joint_name = sys.argv[1]
    servo_position = int(sys.argv[2])

    if joint_name not in JOINTS:
        raise ValueError(f"Unknown joint: {joint_name}")

    if not 0 <= servo_position <= 1000:
        raise ValueError("Servo position must be between 0 and 1000.")

    cfg = JOINTS[joint_name]

    raw_angle = servo_to_rad(
        position=servo_position,
        zero=cfg["zero"],
        direction=cfg["direction"],
        offset_rad=cfg["offset_rad"],
    )

    angle = clamp(raw_angle, cfg["min_rad"], cfg["max_rad"])

    print(f"Joint: {joint_name}")
    print(f"Servo position: {servo_position}")
    print(f"Angle: {angle:.4f} rad")
    print(f"Topic: {cfg['topic']}")

    send_gazebo_command(cfg["topic"], angle)


if __name__ == "__main__":
    main()
