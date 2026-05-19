from pathlib import Path
from types import SimpleNamespace

import numpy as np

import xarm_runtime.onnx_inference as onnx_inference
from xarm_runtime.onnx_inference import _best_box_from_onnx_outputs, _ordered_execution_providers


def test_best_box_from_onnx_outputs_returns_highest_confidence_box() -> None:
    output = np.array(
        [
            [10.0, 20.0, 30.0, 40.0, 0.3, 0.0],
            [100.0, 120.0, 130.0, 140.0, 0.9, 0.0],
        ],
        dtype=np.float32,
    )
    box = _best_box_from_onnx_outputs([output], frame_w=640, frame_h=480, input_w=640, input_h=640, conf_threshold=0.25)
    assert box is not None
    assert (box.x1, box.y1, box.x2, box.y2) == (100.0, 90.0, 130.0, 105.0)


def test_best_box_from_onnx_outputs_returns_none_when_confidence_low() -> None:
    output = np.array([[10.0, 20.0, 30.0, 40.0, 0.1, 0.0]], dtype=np.float32)
    box = _best_box_from_onnx_outputs([output], frame_w=640, frame_h=480, input_w=640, input_h=640, conf_threshold=0.25)
    assert box is None


def test_ordered_execution_providers_prefers_fast_paths(monkeypatch) -> None:
    monkeypatch.delenv("XARM_ORT_PROVIDERS", raising=False)
    providers = _ordered_execution_providers(["CPUExecutionProvider", "CUDAExecutionProvider"])
    assert providers == ("CUDAExecutionProvider", "CPUExecutionProvider")


def test_ordered_execution_providers_respects_override_and_keeps_cpu_fallback(monkeypatch) -> None:
    monkeypatch.setenv("XARM_ORT_PROVIDERS", "CUDAExecutionProvider")
    providers = _ordered_execution_providers(["CPUExecutionProvider", "CUDAExecutionProvider"])
    assert providers == ("CUDAExecutionProvider", "CPUExecutionProvider")


def test_onnx_detector_falls_back_to_cpu_when_preferred_provider_fails(monkeypatch) -> None:
    attempts = []

    class FakeSession:
        def __init__(self, model_path, providers):
            provider = providers[0]
            attempts.append(provider)
            if provider == "CUDAExecutionProvider":
                raise RuntimeError("CUDA unavailable")
            self._providers = providers
            self._inputs = [SimpleNamespace(name="images", shape=[1, 3, 640, 640])]

        def get_inputs(self):
            return self._inputs

        def get_providers(self):
            return self._providers

    fake_ort = SimpleNamespace(
        InferenceSession=FakeSession,
        get_available_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    monkeypatch.setattr(onnx_inference, "ort", fake_ort)
    monkeypatch.delenv("XARM_ORT_PROVIDERS", raising=False)

    detector = onnx_inference.OnnxDetector(Path("model.onnx"))

    assert attempts == ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert detector.providers == ("CPUExecutionProvider",)


def test_create_detector_selects_onnx_backend(monkeypatch) -> None:
    created = []

    class FakeOnnxDetector:
        def __init__(self, model_path, config=None):
            created.append((model_path, config))

    monkeypatch.setattr(onnx_inference, "OnnxDetector", FakeOnnxDetector)

    detector = onnx_inference.create_detector(Path("model.onnx"), config="cfg")

    assert isinstance(detector, FakeOnnxDetector)
    assert created == [(Path("model.onnx"), "cfg")]


def test_create_detector_selects_tensorrt_backend(monkeypatch) -> None:
    created = []

    class FakeTensorRTDetector:
        def __init__(self, model_path, config=None):
            created.append((model_path, config))

    monkeypatch.setattr(onnx_inference, "TensorRTDetector", FakeTensorRTDetector)

    detector = onnx_inference.create_detector(Path("model.engine"), config="cfg")

    assert isinstance(detector, FakeTensorRTDetector)
    assert created == [(Path("model.engine"), "cfg")]


def test_create_detector_rejects_unknown_extension() -> None:
    try:
        onnx_inference.create_detector(Path("model.pt"))
    except ValueError as exc:
        assert "Use .onnx or .engine" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected ValueError for unsupported detector extension")


def test_tensorrt_detector_requires_tensorrt(monkeypatch) -> None:
    monkeypatch.setattr(onnx_inference, "trt", None)

    try:
        onnx_inference.TensorRTDetector(Path("model.engine"))
    except RuntimeError as exc:
        assert "TensorRT is not available" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected RuntimeError when TensorRT import is unavailable")


def test_cuda_runtime_check_raises_on_nonzero_status() -> None:
    try:
        onnx_inference._CudaRuntime._check(13, "cudaMemcpy")
    except RuntimeError as exc:
        assert "cudaMemcpy failed with CUDA status 13" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected RuntimeError for nonzero CUDA status")


def test_first_input_binding_index_returns_input() -> None:
    class FakeEngine:
        num_bindings = 3

        def binding_is_input(self, index):
            return index == 1

    assert onnx_inference._first_input_binding_index(FakeEngine()) == 1


def test_binding_shape_uses_context_shape() -> None:
    class FakeEngine:
        def get_binding_shape(self, index):
            return (-1, 300, 6)

        def get_binding_name(self, index):
            return "output0"

    class FakeContext:
        def get_binding_shape(self, index):
            return (1, 300, 6)

    assert onnx_inference._binding_shape(FakeEngine(), FakeContext(), 0) == (1, 300, 6)


def test_preprocess_frame_casts_to_requested_dtype() -> None:
    frame = np.zeros((4, 4, 3), dtype=np.uint8)

    tensor = onnx_inference._preprocess_frame(frame, 2, 2, np.dtype(np.float16))

    assert tensor.shape == (1, 3, 2, 2)
    assert tensor.dtype == np.float16
    assert tensor.flags["C_CONTIGUOUS"]


def test_require_nbytes_rejects_mismatched_copy_size() -> None:
    array = np.zeros((4,), dtype=np.float32)

    try:
        onnx_inference._require_nbytes(array, 4, "host->device")
    except RuntimeError as exc:
        assert "size mismatch" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected RuntimeError for mismatched TensorRT memcpy size")
