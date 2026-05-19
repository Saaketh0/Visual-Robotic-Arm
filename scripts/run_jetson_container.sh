#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_repo_env() {
  local env_file="$ROOT_DIR/.env"
  if [ -f "$env_file" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$env_file"
    set +a
  fi
}

load_repo_env

WORKSPACE_DIR="${XARM_WS_HOST_DIR:-$ROOT_DIR}"
CONTAINER_WORKSPACE="${XARM_WS_CONTAINER_DIR:-/workspace/xarm_ws}"
CONTAINER_NAME="${JETSON_CONTAINER_NAME:-xarm_ros_humble}"
DEFAULT_JETSON_ROS_IMAGE="dustynv/ros:humble-desktop-l4t-r32.7.1"
AUTOTAG_PACKAGE="${JETSON_AUTOTAG_PACKAGE:-ros:humble-desktop}"
USE_AUTOTAG="${JETSON_USE_AUTOTAG:-0}"
PRINT_IMAGE_ONLY=0

if [ "${1:-}" = "--print-image" ]; then
  PRINT_IMAGE_ONLY=1
  shift
fi

resolve_image() {
  if [ -n "${JETSON_ROS_IMAGE:-}" ]; then
    printf '%s\n' "$JETSON_ROS_IMAGE"
    return 0
  fi

  if [ "$USE_AUTOTAG" = "1" ] || [ "$USE_AUTOTAG" = "true" ]; then
    if command -v autotag >/dev/null 2>&1; then
      autotag "$AUTOTAG_PACKAGE"
      return 0
    fi

    cat >&2 <<EOF2
JETSON_USE_AUTOTAG is enabled but autotag is unavailable.

Install jetson-containers and retry:
  git clone https://github.com/dusty-nv/jetson-containers
  bash jetson-containers/install.sh
EOF2
    return 1
  fi

  printf '%s\n' "$DEFAULT_JETSON_ROS_IMAGE"
}

maybe_add_device() {
  local device_path="$1"
  if [ -e "$device_path" ]; then
    DOCKER_ARGS+=(--device "$device_path")
  fi
}

IMAGE="$(resolve_image)"

if [ "$PRINT_IMAGE_ONLY" -eq 1 ]; then
  printf "%s\n" "$IMAGE"
  exit 0
fi

if [ ! -d "$WORKSPACE_DIR" ]; then
  echo "Workspace directory not found: $WORKSPACE_DIR" >&2
  exit 1
fi

DOCKER_ARGS=(
  --rm
  -it
  --name "$CONTAINER_NAME"
  --network host
  --ipc host
  -v "$WORKSPACE_DIR:$CONTAINER_WORKSPACE"
  -w "$CONTAINER_WORKSPACE"
  -e "XARM_WS_ROOT=$CONTAINER_WORKSPACE"
  -e "XARM_IN_DUSTY_CONTAINER=1"
)

maybe_add_device /dev/video0
maybe_add_device /dev/video1
maybe_add_device /dev/ttyTHS1
maybe_add_device /dev/ttyUSB0

CONTAINER_CMD=(
  /bin/bash
  -lc
  "$CONTAINER_WORKSPACE/scripts/jetson_container_shell.sh \"$CONTAINER_WORKSPACE\""
)

if command -v jetson-containers >/dev/null 2>&1; then
  exec jetson-containers run "${DOCKER_ARGS[@]}" "$IMAGE" "${CONTAINER_CMD[@]}"
fi

if docker info >/dev/null 2>&1; then
  exec docker run --runtime nvidia "${DOCKER_ARGS[@]}" "$IMAGE" "${CONTAINER_CMD[@]}"
fi

exec sudo docker run --runtime nvidia "${DOCKER_ARGS[@]}" "$IMAGE" "${CONTAINER_CMD[@]}"
