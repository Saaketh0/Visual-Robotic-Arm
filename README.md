[Demo Video](https://www.loom.com/share/e1ee984d1a32469cb6eb85cb480af7c0)

Hey there, this is my robotic arm project, that I built partially for my own interest, and partially for my Applied ML class, ECE 629. This project helped me learn ROS2 and Gazebo fundamentals, as well as working on a Jetson board and controlling a robotic arm separetely.

Hope you enjoy, and below is a bunch of helper scripts that I got Codex to generate.


The main package is:

```text
src/xarm_runtime
```

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
## Basic hardware run

```bash
source install/setup.bash
ros2 launch xarm_runtime hardware.launch.py
```

Jetson defaults are in:

```text
src/xarm_runtime/config/jetson.yaml
```

## Jetson helper

To enter the pinned Jetson ROS container on the Jetson:

```bash
./scripts/run_jetson_container.sh
```
Inside the container, build/source the workspace and launch the hardware nodes.
