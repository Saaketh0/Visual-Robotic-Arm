#!/usr/bin/env python3

import subprocess
import time
from pathlib import Path

SCRIPT = str(Path.home() / "ROS2/xarm_ws/xarm_servo_cmd.py")

HOME = {
    "base": 500,
    "shoulder": 500,
    "elbow": 500,
    "wrist_pitch": 500,
    "wrist_roll": 500,
}

for joint, pos in HOME.items():
    print(f"Sending {joint} -> {pos}")
    subprocess.run(["python3", SCRIPT, joint, str(pos)], check=True)
    time.sleep(0.25)

print("Home pose sent.")