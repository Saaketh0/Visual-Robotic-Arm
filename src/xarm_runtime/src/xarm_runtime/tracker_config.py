import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple, Union

CAMERA_DEVICE_CANDIDATES = ("/dev/video1", "/dev/video0")
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
JETSON_CAMERA_FPS = 15
UDP_PORT = 5000


@dataclass(frozen=True)
class TrackerRuntimeConfig:
    use_sim: bool
    is_mac: bool
    platform_profile: str
    camera_device_candidates: Tuple[str, ...]
    camera_width: int
    camera_height: int
    camera_fps: int
    sim_camera_index: int
    enable_udp_preview: bool
    enable_imshow: bool
    laptop_ip: Optional[str]
    model_path_sim: Path
    model_path_real: Path


@dataclass(frozen=True)
class DetectionBox:
    x1: float
    y1: float
    x2: float
    y2: float


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _param(params: Optional[Mapping[str, Any]], name: str, default: Any) -> Any:
    if params is None:
        return default
    value = params.get(name, default)
    return default if value is None else value


def _int_param(params: Optional[Mapping[str, Any]], name: str, default: int) -> int:
    return int(_param(params, name, default))


def _bool_param(params: Optional[Mapping[str, Any]], name: str, default: bool) -> bool:
    value = _param(params, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def parse_camera_candidates(value: Any) -> Tuple[str, ...]:
    if value is None:
        return CAMERA_DEVICE_CANDIDATES
    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",")]
    else:
        candidates = [str(item).strip() for item in value]
    candidates = [item for item in candidates if item]
    if not candidates:
        raise ValueError("camera_device_candidates must include /dev/video0 or /dev/video1")
    invalid = [item for item in candidates if item not in {"/dev/video0", "/dev/video1"}]
    if invalid:
        raise ValueError(
            "Jetson camera candidates are intentionally limited to /dev/video0 and /dev/video1; "
            f"invalid: {tuple(invalid)}"
        )
    return tuple(candidates)


def _first_existing_path(candidates: Iterable[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return next(iter(candidates))


def _workspace_path(workspace_root: Path, value: Union[str, Path]) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else workspace_root / path


def default_model_paths(
    workspace_root: Path,
    model_path_sim: Optional[Union[str, Path]] = None,
    model_path_real: Optional[Union[str, Path]] = None,
) -> Tuple[Path, Path]:
    sim_override = os.getenv("MODEL_PATH_SIM") or model_path_sim
    real_override = os.getenv("MODEL_PATH_REAL") or model_path_real
    if sim_override and real_override:
        return _workspace_path(workspace_root, sim_override), _workspace_path(workspace_root, real_override)

    sim_candidates = [
        workspace_root / "best.onnx",
        workspace_root / "models" / "best.onnx",
        workspace_root / "models" / "exp.onnx",
        workspace_root / "exp.onnx",
    ]
    real_candidates = [
        workspace_root / "best.onnx",
        workspace_root / "models" / "best.onnx",
        workspace_root / "models" / "exp.onnx",
        workspace_root / "exp.onnx",
    ]
    sim_path = _workspace_path(workspace_root, sim_override) if sim_override else _first_existing_path(sim_candidates)
    real_path = _workspace_path(workspace_root, real_override) if real_override else _first_existing_path(real_candidates)
    return sim_path, real_path


def require_existing_model(path: Path, mode: str) -> Path:
    if path.exists():
        return path
    raise FileNotFoundError(
        f"Missing {mode} detector model at {path}. Set MODEL_PATH_{mode.upper()} or update jetson.yaml/model config."
    )


def build_runtime_config(
    workspace_root: Path,
    use_sim: bool,
    is_mac: bool,
    params: Optional[Mapping[str, Any]] = None,
) -> TrackerRuntimeConfig:
    platform_profile = str(_param(params, "platform_profile", "mac_sim" if use_sim and is_mac else "jetson_nano"))
    default_fps = JETSON_CAMERA_FPS if platform_profile == "jetson_nano" and not use_sim else CAMERA_FPS
    model_path_sim, model_path_real = default_model_paths(
        workspace_root,
        _param(params, "model_path_sim", None),
        _param(params, "model_path_real", None),
    )
    return TrackerRuntimeConfig(
        use_sim=use_sim,
        is_mac=is_mac,
        platform_profile=platform_profile,
        camera_device_candidates=parse_camera_candidates(
            _param(params, "camera_device_candidates", CAMERA_DEVICE_CANDIDATES)
        ),
        camera_width=_int_param(params, "camera_width", CAMERA_WIDTH),
        camera_height=_int_param(params, "camera_height", CAMERA_HEIGHT),
        camera_fps=_int_param(params, "camera_fps", default_fps),
        sim_camera_index=_int_param(params, "sim_camera_index", int(os.environ.get("SIM_CAMERA_INDEX", "0"))),
        enable_udp_preview=env_flag("ENABLE_UDP_PREVIEW", _bool_param(params, "enable_udp_preview", False)),
        enable_imshow=env_flag("ENABLE_IMSHOW", _bool_param(params, "enable_imshow", use_sim)),
        laptop_ip=os.getenv("LAPTOP_IP"),
        model_path_sim=model_path_sim,
        model_path_real=model_path_real,
    )


def select_linux_camera_device(candidates: Iterable[str] = CAMERA_DEVICE_CANDIDATES) -> str:
    for device in candidates:
        if not os.path.exists(device):
            continue
        try:
            fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
            os.close(fd)
            return device
        except OSError:
            continue
    raise RuntimeError(f"No available camera device found in {tuple(candidates)}")


def compute_pixel_error(
    box: DetectionBox,
    frame_width: int,
    frame_height: int,
    scaled_width: int = CAMERA_WIDTH,
    scaled_height: int = CAMERA_HEIGHT,
) -> Tuple[float, float]:
    x_mid = frame_width / 2.0
    y_mid = frame_height / 2.0
    x_center = 0.5 * (box.x1 + box.x2)
    y_center = 0.5 * (box.y1 + box.y2)
    scale_x = scaled_width / float(frame_width)
    scale_y = scaled_height / float(frame_height)
    return float((x_mid - x_center) * scale_x), float((y_mid - y_center) * scale_y)
