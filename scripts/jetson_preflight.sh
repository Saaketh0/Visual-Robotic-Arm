#!/usr/bin/env bash
set -euo pipefail

SKIP_HARDWARE=0

usage() {
  cat <<'EOF2'
Usage: scripts/jetson_preflight.sh [--skip-hardware]

Checks whether the current environment looks ready for the Jetson Nano runtime.
Use --skip-hardware when you want to validate software packages without a camera
or serial device physically attached.
EOF2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-hardware|-S)
      SKIP_HARDWARE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="${XARM_WS_ROOT:-$ROOT_DIR}"
JETSON_YAML="$WORKSPACE_ROOT/src/xarm_runtime/config/jetson.yaml"
IN_DUSTY_CONTAINER="${XARM_IN_DUSTY_CONTAINER:-0}"

passes=0
warnings=0
failures=0

log() {
  printf '%s\n' "$*"
}

pass() {
  passes=$((passes + 1))
  log "[PASS] $*"
}

warn() {
  warnings=$((warnings + 1))
  log "[WARN] $*"
}

fail() {
  failures=$((failures + 1))
  log "[FAIL] $*"
}

check_file() {
  local path="$1"
  local label="$2"
  if [ -f "$path" ]; then
    pass "$label found: $path"
  else
    fail "$label missing: $path"
  fi
}

check_device() {
  local path="$1"
  if [ -e "$path" ]; then
    pass "device present: $path"
  else
    warn "device missing: $path"
  fi
}

log "Jetson Nano preflight"
log "Workspace root: $WORKSPACE_ROOT"

case "$(uname -s)" in
  Linux) pass "host OS is Linux" ;;
  *) fail "host OS is not Linux (found: $(uname -s))" ;;
esac

case "$(uname -m)" in
  aarch64|arm64) pass "architecture is Jetson-compatible ($(uname -m))" ;;
  *) fail "architecture is not Jetson-compatible (found: $(uname -m))" ;;
esac

if [ -n "${CONDA_PREFIX:-}" ]; then
  warn "conda is active at $CONDA_PREFIX; mixed conda/system libraries can cause import problems"
else
  pass "conda is not active"
fi

if [ -x /opt/ros/humble/setup.bash ] || [ -f /opt/ros/humble/setup.bash ]; then
  pass "ROS 2 Humble setup script exists at /opt/ros/humble/setup.bash"
elif [ -x /opt/ros/humble/install/setup.bash ] || [ -f /opt/ros/humble/install/setup.bash ]; then
  pass "ROS 2 Humble setup script exists at /opt/ros/humble/install/setup.bash"
else
  warn "ROS 2 Humble setup script not found at /opt/ros/humble/setup.bash or /opt/ros/humble/install/setup.bash"
fi

if command -v ros2 >/dev/null 2>&1; then
  pass "ros2 command is available"
else
  fail "ros2 command is not in PATH"
fi

if command -v python3 >/dev/null 2>&1; then
  pass "python3 command is available"
else
  fail "python3 command is not in PATH"
fi

check_file "$JETSON_YAML" "Jetson runtime config"
check_file "$WORKSPACE_ROOT/src/xarm_runtime/src/xarm_runtime/tracker_node.py" "tracker node"

model_candidates=(
  "$WORKSPACE_ROOT/models/exp.onnx"
  "$WORKSPACE_ROOT/exp.onnx"
  "$WORKSPACE_ROOT/models/best.onnx"
  "$WORKSPACE_ROOT/best.onnx"
)
selected_model=""
for candidate in "${model_candidates[@]}"; do
  if [ -f "$candidate" ]; then
    selected_model="$candidate"
    break
  fi
done

if [ -n "$selected_model" ]; then
  pass "ONNX model available: $selected_model"
else
  fail "no ONNX model found in any expected location: ${model_candidates[*]}"
fi

log ""
log "Python import check"
set +e
python_output="$(python3 -u <<'PY'
import importlib
import os
import platform
import sys

modules = ["numpy", "cv2", "onnxruntime", "serial"]
if "ROS_DISTRO" in os.environ or "AMENT_PREFIX_PATH" in os.environ:
    modules.append("rclpy")

print(f"python: {sys.executable}")
print(f"platform: {platform.platform()}")
print(f"machine: {platform.machine()}")

python_failures = 0
missing_ort = False
for name in modules:
    try:
        mod = importlib.import_module(name)
    except Exception as exc:
        print(f"[FAIL] import {name}: {exc}")
        python_failures += 1
        if name == "onnxruntime":
            missing_ort = True
        continue

    version = getattr(mod, "__version__", None)
    if name == "onnxruntime" and hasattr(mod, "get_available_providers"):
        print(f"[PASS] import {name}: version={version} providers={mod.get_available_providers()}")
    elif name == "onnxruntime" and hasattr(mod, "get_device"):
        print(f"[PASS] import {name}: version={version} device={mod.get_device()}")
    else:
        print(f"[PASS] import {name}: version={version}")

if python_failures:
    raise SystemExit(20 if missing_ort else 10)
PY
)"
python_status=$?
set -e
if [ "$python_status" -ne 0 ]; then
  printf '%s\n' "$python_output"
  if [ "$python_status" -eq 20 ]; then
    fail "onnxruntime is required for detector runtime readiness. Rebuild Dockerfile.jetson with a Jetson-specific ONNX Runtime layer or start from a Dusty image that already imports onnxruntime."
  else
    fail "Python import check failed. Fix the import errors above before launching xarm_runtime."
  fi
  exit 1
fi
printf '%s\n' "$python_output"
pass "Python imports look good"

if [ "$IN_DUSTY_CONTAINER" = "1" ] || [ -f /.dockerenv ]; then
  pass "container marker detected for Jetson image workflow"
else
  warn "container marker not detected; canonical Jetson runtime path is Dockerfile.jetson or scripts/run_jetson_container.sh"
fi

if [ "$SKIP_HARDWARE" -eq 0 ]; then
  log ""
  log "Hardware check"
  if [ -e /dev/video0 ] || [ -e /dev/video1 ]; then
    pass "at least one camera device exists in /dev/video0 or /dev/video1"
    check_device /dev/video0
    check_device /dev/video1
  else
    fail "no camera device found at /dev/video0 or /dev/video1"
  fi

  if [ -e /dev/ttyTHS1 ] || [ -e /dev/ttyUSB0 ]; then
    pass "at least one serial device exists in /dev/ttyTHS1 or /dev/ttyUSB0"
    check_device /dev/ttyTHS1
    check_device /dev/ttyUSB0
  else
    fail "no serial device found at /dev/ttyTHS1 or /dev/ttyUSB0"
  fi
fi

log ""
log "Summary: ${passes} passed, ${warnings} warnings, ${failures} failures"

if [ "$failures" -ne 0 ]; then
  exit 1
fi

exit 0
