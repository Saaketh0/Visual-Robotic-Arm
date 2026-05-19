from typing import Iterable, Iterator, Mapping, Optional, Tuple

from xarm_runtime.joint_model import JOINTS, JOINT_ORDER, MIN_DELTA_COUNTS, clamp, joint_angle_to_counts


def move_servo_packet(servo_id: int, position: int, move_time_ms: int) -> bytearray:
    position = int(max(0, min(1000, position)))
    move_time_ms = int(max(0, min(30000, move_time_ms)))
    return bytearray([
        0x55,
        0x55,
        0x08,
        0x03,
        0x01,
        move_time_ms & 0xFF,
        (move_time_ms >> 8) & 0xFF,
        servo_id,
        position & 0xFF,
        (position >> 8) & 0xFF,
    ])


def compute_servo_writes(
    values: Iterable[float],
    last_counts: Mapping[str, Optional[int]],
    joints: Mapping[str, Mapping[str, float]] = JOINTS,
) -> Iterator[Tuple[str, int, int]]:
    for name, angle in zip(JOINT_ORDER, values):
        cfg = joints[name]
        bounded_angle = clamp(float(angle), cfg["min_rad"], cfg["max_rad"])
        counts = joint_angle_to_counts(bounded_angle, cfg)
        prev = last_counts.get(name)
        if prev is not None and abs(counts - prev) < MIN_DELTA_COUNTS:
            continue
        yield name, int(cfg["servo_id"]), counts
