import importlib.util
from pathlib import Path

from launch import LaunchDescription
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parents[1]


def _load_launch(name: str):
    path = ROOT / 'launch' / name
    spec = importlib.util.spec_from_file_location(name.replace('.', '_'), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _parameter_file_paths(params) -> list[str]:
    paths = []
    for param in params:
        for substitution in param.param_file:
            paths.append(str(substitution.text))
    return paths


def test_launch_modules_generate_descriptions() -> None:
    for name in ('hardware.launch.py',):
        module = _load_launch(name)
        desc = module.generate_launch_description()
        assert isinstance(desc, LaunchDescription)


def test_hardware_launch_loads_jetson_config() -> None:
    module = _load_launch("hardware.launch.py")
    desc = module.generate_launch_description()
    node_params = [
        entity._Node__parameters
        for entity in desc.entities
        if isinstance(entity, Node) and entity.node_executable in {"tracker_node", "device_backend_node"}
    ]

    assert len(node_params) == 2
    assert all(any(path.endswith("config/jetson.yaml") for path in _parameter_file_paths(params)) for params in node_params)
