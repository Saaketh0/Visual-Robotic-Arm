from xarm_runtime.backends.serial_device import compute_servo_writes, move_servo_packet


def test_move_servo_packet_layout() -> None:
    packet = move_servo_packet(6, 500, 80)
    assert list(packet[:4]) == [0x55, 0x55, 0x08, 0x03]
    assert packet[7] == 6


def test_compute_servo_writes_skips_small_deltas() -> None:
    last_counts = {"base": 500, "shoulder": None, "elbow": None, "camera": None}
    writes = list(compute_servo_writes([0.0, 0.0, 0.0, 0.0], last_counts))
    assert all(name != "base" for name, _, _ in writes)
    assert {name for name, _, _ in writes} == {"shoulder", "elbow", "camera"}
