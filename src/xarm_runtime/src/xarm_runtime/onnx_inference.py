import ctypes
import ctypes.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

from xarm_runtime.tracker_config import DetectionBox

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - resolved at runtime on target env
    ort = None

try:
    import tensorrt as trt
except Exception:  # pragma: no cover - resolved at runtime on Jetson target env
    trt = None

PREFERRED_EXECUTION_PROVIDERS = (
    "TensorrtExecutionProvider",
    "CUDAExecutionProvider",
    "CPUExecutionProvider",
)
CUDA_MEMCPY_HOST_TO_DEVICE = 1
CUDA_MEMCPY_DEVICE_TO_HOST = 2


@dataclass(frozen=True)
class OnnxDetectorConfig:
    conf_threshold: float = 0.25


class OnnxDetector:
    backend_name = "onnxruntime"

    def __init__(self, model_path: Path, config: Optional[OnnxDetectorConfig] = None):
        if ort is None:
            raise RuntimeError(
                "onnxruntime is not available. On Jetson, rebuild Dockerfile.jetson with a Jetson-specific ONNX Runtime layer "
                "or start from a Dusty image that already imports onnxruntime."
            )
        self._config = config or OnnxDetectorConfig()
        self._session, self.providers = _create_inference_session(model_path)
        self._input_name = self._session.get_inputs()[0].name
        input_shape = self._session.get_inputs()[0].shape
        self._input_h = int(input_shape[2]) if len(input_shape) > 2 and isinstance(input_shape[2], int) else 640
        self._input_w = int(input_shape[3]) if len(input_shape) > 3 and isinstance(input_shape[3], int) else 640

    def detect_best_box(self, frame: np.ndarray) -> Optional[DetectionBox]:
        frame_h, frame_w = frame.shape[:2]
        tensor = _preprocess_frame(frame, self._input_w, self._input_h)
        outputs = self._session.run(None, {self._input_name: tensor})
        return _best_box_from_onnx_outputs(outputs, frame_w, frame_h, self._input_w, self._input_h, self._config.conf_threshold)


class TensorRTDetector:
    backend_name = "tensorrt"

    def __init__(self, engine_path: Path, config: Optional[OnnxDetectorConfig] = None):
        if trt is None:
            raise RuntimeError(
                "TensorRT is not available. Use the Jetson Docker image/runtime that imports `tensorrt`, "
                "or use a .onnx model with the ONNX Runtime backend."
            )
        self._config = config or OnnxDetectorConfig()
        self.providers = ("TensorRT", "CUDA")
        self._logger = trt.Logger(trt.Logger.WARNING)
        self._runtime = trt.Runtime(self._logger)
        engine_bytes = Path(engine_path).read_bytes()
        self._engine = self._runtime.deserialize_cuda_engine(engine_bytes)
        if self._engine is None:
            raise RuntimeError(f"TensorRT could not deserialize engine at {engine_path}")
        self._context = self._engine.create_execution_context()
        if self._context is None:
            raise RuntimeError(f"TensorRT could not create execution context for {engine_path}")
        self._cuda = _CudaRuntime()
        self._bindings: List[int] = [0] * int(self._engine.num_bindings)
        self._device_allocations: Dict[int, int] = {}
        self._binding_nbytes: Dict[int, int] = {}
        self._binding_dtypes: Dict[int, np.dtype] = {}
        self._host_outputs: Dict[int, np.ndarray] = {}
        self._output_binding_indices: List[int] = []
        self._input_index = _first_input_binding_index(self._engine)
        input_shape = tuple(int(dim) for dim in self._engine.get_binding_shape(self._input_index))
        if len(input_shape) != 4:
            raise RuntimeError(f"TensorRT engine input must be NCHW, got shape {input_shape}")
        if any(dim < 0 for dim in input_shape):
            # The exported face model is static. This fallback makes dynamic engines usable
            # for the same 640x640 YOLO family without adding new ROS parameters.
            input_shape = (1, 3, 640, 640)
            self._context.set_binding_shape(self._input_index, input_shape)
        self._input_shape = input_shape
        self._input_h = int(input_shape[2])
        self._input_w = int(input_shape[3])
        self._allocate_bindings()

    def detect_best_box(self, frame: np.ndarray) -> Optional[DetectionBox]:
        frame_h, frame_w = frame.shape[:2]
        tensor = _preprocess_frame(frame, self._input_w, self._input_h, self._binding_dtypes[self._input_index])
        self._cuda.memcpy_host_to_device(
            self._device_allocations[self._input_index],
            tensor,
            self._binding_nbytes[self._input_index],
        )
        ok = self._context.execute_v2(self._bindings)
        if not ok:
            raise RuntimeError("TensorRT execution failed")
        outputs: List[np.ndarray] = []
        for binding_index in self._output_binding_indices:
            output = self._host_outputs[binding_index]
            self._cuda.memcpy_device_to_host(
                output,
                self._device_allocations[binding_index],
                self._binding_nbytes[binding_index],
            )
            outputs.append(output.copy())
        return _best_box_from_onnx_outputs(outputs, frame_w, frame_h, self._input_w, self._input_h, self._config.conf_threshold)

    def close(self) -> None:
        for ptr in list(self._device_allocations.values()):
            self._cuda.free(ptr)
        self._device_allocations.clear()
        self._bindings = []

    def __del__(self):  # pragma: no cover - best-effort cleanup at interpreter shutdown
        try:
            self.close()
        except Exception:
            pass

    def _allocate_bindings(self) -> None:
        for binding_index in range(int(self._engine.num_bindings)):
            shape = _binding_shape(self._engine, self._context, binding_index)
            dtype = np.dtype(trt.nptype(self._engine.get_binding_dtype(binding_index)))
            nbytes = int(np.prod(shape)) * dtype.itemsize
            ptr = self._cuda.malloc(nbytes)
            self._binding_dtypes[binding_index] = dtype
            self._binding_nbytes[binding_index] = nbytes
            self._device_allocations[binding_index] = ptr
            self._bindings[binding_index] = ptr
            if not self._engine.binding_is_input(binding_index):
                self._output_binding_indices.append(binding_index)
                self._host_outputs[binding_index] = np.empty(shape, dtype=dtype)


class _CudaRuntime:
    def __init__(self) -> None:
        lib_path = ctypes.util.find_library("cudart") or "libcudart.so"
        self._lib = ctypes.CDLL(lib_path)

    def malloc(self, nbytes: int) -> int:
        ptr = ctypes.c_void_p()
        self._check(self._lib.cudaMalloc(ctypes.byref(ptr), ctypes.c_size_t(nbytes)), "cudaMalloc")
        if ptr.value is None:
            raise RuntimeError("cudaMalloc returned a null pointer")
        return int(ptr.value)

    def free(self, ptr: int) -> None:
        if ptr:
            self._check(self._lib.cudaFree(ctypes.c_void_p(ptr)), "cudaFree")

    def memcpy_host_to_device(self, device_ptr: int, host_array: np.ndarray, expected_nbytes: int) -> None:
        contiguous = np.ascontiguousarray(host_array)
        _require_nbytes(contiguous, expected_nbytes, "host->device")
        self._check(
            self._lib.cudaMemcpy(
                ctypes.c_void_p(device_ptr),
                ctypes.c_void_p(contiguous.ctypes.data),
                ctypes.c_size_t(expected_nbytes),
                ctypes.c_int(CUDA_MEMCPY_HOST_TO_DEVICE),
            ),
            "cudaMemcpy host->device",
        )

    def memcpy_device_to_host(self, host_array: np.ndarray, device_ptr: int, expected_nbytes: int) -> None:
        contiguous = np.ascontiguousarray(host_array)
        _require_nbytes(contiguous, expected_nbytes, "device->host")
        self._check(
            self._lib.cudaMemcpy(
                ctypes.c_void_p(contiguous.ctypes.data),
                ctypes.c_void_p(device_ptr),
                ctypes.c_size_t(expected_nbytes),
                ctypes.c_int(CUDA_MEMCPY_DEVICE_TO_HOST),
            ),
            "cudaMemcpy device->host",
        )
        if contiguous.ctypes.data != host_array.ctypes.data:
            host_array[...] = contiguous.reshape(host_array.shape)

    @staticmethod
    def _check(status: int, operation: str) -> None:
        if int(status) != 0:
            raise RuntimeError(f"{operation} failed with CUDA status {status}")


def create_detector(model_path: Path, config: Optional[OnnxDetectorConfig] = None):
    suffix = Path(model_path).suffix.lower()
    if suffix == ".onnx":
        return OnnxDetector(model_path, config)
    if suffix == ".engine":
        return TensorRTDetector(model_path, config)
    raise ValueError(f"Unsupported detector model extension '{suffix}'. Use .onnx or .engine.")


def _preprocess_frame(frame: np.ndarray, input_w: int, input_h: int, dtype: np.dtype = np.dtype(np.float32)) -> np.ndarray:
    resized = cv2.resize(frame, (input_w, input_h))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))
    tensor = np.expand_dims(tensor, axis=0)
    return np.ascontiguousarray(tensor.astype(dtype, copy=False))


def _require_nbytes(array: np.ndarray, expected_nbytes: int, direction: str) -> None:
    if int(array.nbytes) != int(expected_nbytes):
        raise RuntimeError(
            f"TensorRT cudaMemcpy {direction} size mismatch: host buffer has {array.nbytes} bytes, "
            f"binding expects {expected_nbytes} bytes"
        )


def _first_input_binding_index(engine) -> int:
    for binding_index in range(int(engine.num_bindings)):
        if engine.binding_is_input(binding_index):
            return binding_index
    raise RuntimeError("TensorRT engine has no input binding")


def _binding_shape(engine, context, binding_index: int) -> Tuple[int, ...]:
    shape = tuple(int(dim) for dim in context.get_binding_shape(binding_index))
    if not shape or any(dim < 0 for dim in shape):
        shape = tuple(int(dim) for dim in engine.get_binding_shape(binding_index))
    if not shape or any(dim < 0 for dim in shape):
        name = engine.get_binding_name(binding_index)
        raise RuntimeError(f"TensorRT binding {name} has unresolved dynamic shape {shape}")
    return shape


def _provider_override() -> Tuple[str, ...]:
    raw = os.getenv("XARM_ORT_PROVIDERS", "")
    providers = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(providers)


def _ordered_execution_providers(available_providers: Union[List[str], Tuple[str, ...]]) -> Tuple[str, ...]:
    available = tuple(available_providers)
    requested = _provider_override()
    if requested:
        ordered = [provider for provider in requested if provider in available]
        if "CPUExecutionProvider" in available and "CPUExecutionProvider" not in ordered:
            ordered.append("CPUExecutionProvider")
        return tuple(ordered)

    ordered = [provider for provider in PREFERRED_EXECUTION_PROVIDERS if provider in available]
    ordered.extend(provider for provider in available if provider not in ordered)
    return tuple(ordered)


def _create_inference_session(model_path: Path):
    available = tuple(getattr(ort, "get_available_providers", lambda: [])())
    ordered = _ordered_execution_providers(available)
    if not ordered:
        raise RuntimeError("onnxruntime reported no execution providers. Install a Jetson-compatible ONNX Runtime build.")

    errors: List[str] = []
    for provider in ordered:
        try:
            session = ort.InferenceSession(str(model_path), providers=[provider])
            active_providers = tuple(getattr(session, "get_providers", lambda: [provider])())
            return session, active_providers
        except Exception as exc:  # pragma: no cover - target-specific provider failures
            errors.append(f"{provider}: {exc}")

    joined_errors = "; ".join(errors)
    raise RuntimeError(f"Could not create ONNX Runtime session for {model_path}. Tried providers {ordered}. Errors: {joined_errors}")


def _best_box_from_onnx_outputs(
    outputs: Sequence[object],
    frame_w: int,
    frame_h: int,
    input_w: int,
    input_h: int,
    conf_threshold: float,
) -> Optional[DetectionBox]:
    for output in outputs:
        if not isinstance(output, np.ndarray):
            continue
        data = output
        if data.ndim == 3 and data.shape[0] == 1:
            data = data[0]
        if data.ndim != 2 or data.shape[1] < 6:
            continue
        confidences = data[:, 4]
        best_idx = int(np.argmax(confidences))
        best_conf = float(confidences[best_idx])
        if best_conf < conf_threshold:
            return None
        x1, y1, x2, y2 = data[best_idx, :4].tolist()
        scale_x = float(frame_w) / float(input_w)
        scale_y = float(frame_h) / float(input_h)
        return DetectionBox(float(x1 * scale_x), float(y1 * scale_y), float(x2 * scale_x), float(y2 * scale_y))
    return None
