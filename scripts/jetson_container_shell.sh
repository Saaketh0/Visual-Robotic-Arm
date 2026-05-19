#!/usr/bin/env bash
set -eo pipefail

WORKSPACE_DIR="${1:-/workspace/xarm_ws}"

if [ ! -d "$WORKSPACE_DIR" ]; then
  echo "Workspace directory not found: $WORKSPACE_DIR" >&2
  exit 1
fi

cd "$WORKSPACE_DIR"

if [ -f "$WORKSPACE_DIR/.env" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$WORKSPACE_DIR/.env"
  set +a
fi

if [ -f /opt/ros/humble/install/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/install/setup.bash
elif [ -f /opt/ros/humble/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
else
  echo "ROS Humble setup.bash not found inside container." >&2
fi

export XARM_WS_ROOT="$WORKSPACE_DIR"
export XARM_IN_DUSTY_CONTAINER=1

if [ -f install/setup.bash ]; then
  set +u
  # shellcheck disable=SC1091
  source install/setup.bash
  set -u 2>/dev/null || true
else
  echo "Workspace is not built yet. Build with:"
  echo "  colcon build --symlink-install --packages-select xarm_runtime xarm_1s_description xarm_tuning_tools"
fi

echo "Jetson ROS shell ready in $WORKSPACE_DIR"
exec /bin/bash -i
