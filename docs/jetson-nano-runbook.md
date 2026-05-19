# Jetson Nano Runbook

This runbook is for Jetson Nano hardware bring-up using the pinned Dusty-NV ROS 2 Humble image family.

## Canonical vs fallback path
Use one of these two paths:

1. **Canonical packaged image** — build `Dockerfile.jetson` from `dustynv/ros:humble-desktop-l4t-r32.7.1` and run that image for reproducible runtime behavior.
2. **Fallback Dusty shell** — use `./scripts/run_jetson_container.sh` to open the pinned base image with your workspace mounted for manual inspection or recovery.

Reference image family:
- https://github.com/dusty-nv/jetson-containers/blob/master/packages/physicalAI/ros/README.md

## 0. Build the canonical Jetson image
```bash
cd /path/to/xarm_ws

docker build \
  -f Dockerfile.jetson \
  -t xarm-jetson:humble-r32.7.1 \
  .
```

If `onnxruntime` is not already available in the base image, rebuild with a Jetson-specific wheel URL:
```bash
docker build \
  -f Dockerfile.jetson \
  -t xarm-jetson:humble-r32.7.1 \
  --build-arg XARM_JETSON_ORT_WHEEL_URL="https://.../onnxruntime-jetson.whl" \
  .
```

The build must succeed with:
- `import numpy`
- `import cv2`
- `import onnxruntime`
- `import serial`
- `import rclpy`

If `import onnxruntime` still fails, the image is **not runtime-ready** for the detector.

## 1. Run the canonical Jetson image
```bash
docker run --rm -it \
  --runtime nvidia \
  --network host \
  --ipc host \
  --device /dev/video0 \
  --device /dev/ttyTHS1 \
  xarm-jetson:humble-r32.7.1
```

The image bakes in:
- `/workspace/xarm_ws`
- `XARM_WS_ROOT=/workspace/xarm_ws`
- `XARM_IN_DUSTY_CONTAINER=1`
- a built workspace overlay
- `models/exp.onnx` copied from the repo root `exp.onnx`

## 2. Fallback: enter the pinned Dusty base image with your workspace mounted
```bash
cd /path/to/xarm_ws
./scripts/run_jetson_container.sh
```

Notes:
- default image: `dustynv/ros:humble-desktop-l4t-r32.7.1`
- override with `JETSON_ROS_IMAGE=...`
- opt into `autotag` with `JETSON_USE_AUTOTAG=1`

Once inside the fallback container, you will land in a shell with:
- `/opt/ros/humble/setup.bash` sourced when present
- `XARM_WS_ROOT=/workspace/xarm_ws`
- `XARM_IN_DUSTY_CONTAINER=1`
- `install/setup.bash` sourced if the workspace was already built

## 3. Preflight the environment
If you want a fast readiness check before launching anything, run:

```bash
./scripts/jetson_preflight.sh --skip-hardware
```

Interpretation:
- missing `onnxruntime` is a **FAIL** for runtime readiness
- if you are outside the canonical Jetson image path, the script will tell you to rebuild `Dockerfile.jetson` or use the pinned Dusty container helper

## 4. Verify devices
```bash
ls -l /dev/video0 /dev/video1 2>/dev/null || true
ls -l /dev/ttyTHS1 /dev/ttyUSB0 2>/dev/null || true
```

The runtime intentionally defaults to camera candidates `/dev/video0` and `/dev/video1` only. The default serial port is `/dev/ttyTHS1`.

If serial permissions fail, add the Jetson user to the serial-owning group for your device, then log out and back in. Common groups are `dialout` for USB serial and `tty` for onboard UART.

## 5. Model assets
Preferred layout inside the image or mounted workspace:

```text
models/exp.onnx
```

Temporary fallback during migration:

```text
exp.onnx
```

The macOS simulation model remains separate (`best.mlpackage`). Jetson hardware should use the ONNX model path from `src/xarm_runtime/config/jetson.yaml`.

## 6. Build and source (fallback shell path)
If you entered the fallback Dusty shell rather than running the packaged image, build manually:

```bash
cd /path/to/xarm_ws
colcon build --packages-select xarm_runtime xarm_1s_description xarm_tuning_tools
source install/setup.bash
```

## 7. Launch hardware stack
`hardware.launch.py` loads `config/jetson.yaml` by default.

```bash
ros2 launch xarm_runtime hardware.launch.py
```

Override serial settings when needed:

```bash
ros2 launch xarm_runtime hardware.launch.py --ros-args \
  -p serial_port:=/dev/ttyUSB0 \
  -p baudrate:=9600 \
  -p move_time_ms:=80
```

The tracker will log the model path and active ONNX Runtime providers at startup.

## 8. Monitor runtime topics
```bash
ros2 topic hz /pixel_error
ros2 topic echo /pixel_error
ros2 topic hz /joint_cmds
ros2 topic echo /joint_cmds
```

## 9. Stop safely
Use `Ctrl-C` in the launch terminal. If a process is stuck:

```bash
pkill -f tracker_node || true
pkill -f device_backend_node || true
```

Physically keep the arm clear during first motion tests and start with conservative servo timing in `jetson.yaml`.
