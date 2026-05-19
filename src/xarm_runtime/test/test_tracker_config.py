from pathlib import Path

import pytest

from xarm_runtime.tracker_config import (
    DetectionBox,
    build_runtime_config,
    compute_pixel_error,
    default_model_paths,
    env_flag,
    parse_camera_candidates,
    require_existing_model,
)


def test_env_flag_parses_truthy_and_falsey(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_IMSHOW", "false")
    assert env_flag("ENABLE_IMSHOW", True) is False
    monkeypatch.setenv("ENABLE_IMSHOW", "yes")
    assert env_flag("ENABLE_IMSHOW", False) is True


def test_compute_pixel_error_returns_center_relative_offsets() -> None:
    box = DetectionBox(300.0, 220.0, 340.0, 260.0)
    assert compute_pixel_error(box, 640, 480) == (0.0, 0.0)


def test_build_runtime_config_uses_workspace_defaults(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_PATH_REAL", raising=False)
    cfg = build_runtime_config(Path('/tmp/ws'), use_sim=False, is_mac=False)
    assert str(cfg.model_path_real).endswith('/tmp/ws/best.onnx')
    assert cfg.camera_device_candidates == ("/dev/video1", "/dev/video0")
    assert cfg.camera_fps == 15


def test_default_model_paths_prefer_workspace_and_env(monkeypatch, tmp_path) -> None:
    sim_model = tmp_path / "best.onnx"
    best_real_model = tmp_path / "best.onnx"
    real_model = tmp_path / "exp.onnx"
    sim_model.write_text("sim")
    best_real_model.write_text("best")
    real_model.write_text("real")
    monkeypatch.delenv("MODEL_PATH_SIM", raising=False)
    monkeypatch.delenv("MODEL_PATH_REAL", raising=False)
    sim_path, real_path = default_model_paths(tmp_path)
    assert sim_path == sim_model
    assert real_path == best_real_model


def test_jetson_params_override_runtime_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MODEL_PATH_REAL", raising=False)
    cfg = build_runtime_config(
        tmp_path,
        use_sim=False,
        is_mac=False,
        params={
            "platform_profile": "jetson_nano",
            "camera_device_candidates": ["/dev/video0", "/dev/video1"],
            "camera_width": 320,
            "camera_height": 240,
            "camera_fps": 10,
            "enable_imshow": False,
            "enable_udp_preview": False,
            "model_path_real": "models/exp.onnx",
        },
    )

    assert cfg.camera_device_candidates == ("/dev/video0", "/dev/video1")
    assert cfg.camera_width == 320
    assert cfg.camera_height == 240
    assert cfg.camera_fps == 10
    assert cfg.enable_imshow is False
    assert cfg.enable_udp_preview is False
    assert cfg.model_path_real == tmp_path / "models" / "exp.onnx"


def test_camera_candidates_are_limited_to_declared_jetson_devices() -> None:
    assert parse_camera_candidates("/dev/video0,/dev/video1") == ("/dev/video0", "/dev/video1")
    with pytest.raises(ValueError, match="/dev/video0 and /dev/video1"):
        parse_camera_candidates(["/dev/video2"])


def test_require_existing_model_reports_missing_path(tmp_path) -> None:
    missing = tmp_path / "models" / "exp.onnx"
    with pytest.raises(FileNotFoundError, match="Missing real detector model"):
        require_existing_model(missing, "real")
