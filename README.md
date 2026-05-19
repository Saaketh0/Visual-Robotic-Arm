# xArm ROS2 Runtime

ROS2 workspace for running a camera-tracked LewanSoul/xArm-style robot arm.

The main package is:

```text
src/xarm_runtime
```

It contains:

- camera/object tracking node
- ONNX/TensorRT model runtime wrapper
- servo controller node
- serial hardware backend
- simple tests and Jetson helper scripts

## Model weights are not included

Model files are intentionally ignored and are not committed to this repo.
Before running the tracker, add your own model locally.

Expected Jetson paths:

```text
models/exp.onnx
models/exp.engine   # optional TensorRT engine
```

For the Docker build path, the current `Dockerfile.jetson` expects local files at:

```text
exp.onnx
best.onnx
```

Those files should stay local unless you have the right to redistribute them.

## Basic build

From the workspace root:

```bash
colcon build --packages-select xarm_runtime xarm_1s_description xarm_tuning_tools
source install/setup.bash
```

## Basic test

```bash
./scripts/test_runtime.sh
```

## Basic hardware run

```bash
source install/setup.bash
ros2 launch xarm_runtime hardware.launch.py
```

Jetson defaults are in:

```text
src/xarm_runtime/config/jetson.yaml
```

## Local settings

Machine-specific values belong in `.env`, which is ignored by git.
Use `.env.example` as the template.

Examples:

```bash
cp .env.example .env
```

Then edit `.env` for your machine.

## Jetson helper

To enter the pinned Jetson ROS container on the Jetson:

```bash
./scripts/run_jetson_container.sh
```

Inside the container, build/source the workspace and launch the hardware nodes.

## Notes

- `build/`, `install/`, and `log/` are generated and ignored.
- Model artifacts such as `.onnx`, `.engine`, `.pt`, and `.mlpackage` are ignored.
- Runtime captures/videos are ignored.
- Legacy discarded code is ignored under `trash/` and `extra_scripts/`.
