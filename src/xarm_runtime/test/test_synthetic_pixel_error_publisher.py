from xarm_runtime.synthetic_pixel_error_publisher import PathConfig, assemble_path


def test_assemble_path_is_deterministic_and_nonempty() -> None:
    cfg = PathConfig(
        max_x=160.0,
        max_y=120.0,
        step_px=20.0,
        publish_rate_hz=20.0,
        corner_dwell_sec=0.2,
        spiral_turns=4,
        spiral_inward_step=20.0,
        loop=True,
    )
    path = assemble_path(cfg)
    assert path[0] == (0.0, 0.0)
    assert len(path) > 50
