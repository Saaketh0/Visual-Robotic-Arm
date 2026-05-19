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

CONTAINER_NAME="${CONTAINER_NAME:-xarm_ros_humble}"
XAUTH_FILE="${XAUTH_FILE:-/tmp/.docker-xauth-${USER:-jetson}}"
CONTAINER_XAUTH="/tmp/.docker.xauth"
JETSON_SSH_USER="${JETSON_SSH_USER:-}"
JETSON_SSH_HOST="${JETSON_SSH_HOST:-}"

if [[ -z "${DISPLAY:-}" ]]; then
  if [ -n "$JETSON_SSH_USER" ]; then
    local_ssh_target="${JETSON_SSH_USER}@${JETSON_SSH_HOST:-<jetson-host>}"
  else
    local_ssh_target="${JETSON_SSH_HOST:-<jetson-host>}"
  fi
  cat >&2 <<'EOF'
DISPLAY is not set.

Start from your laptop with X11 forwarding, for example:
EOF
  printf '  ssh -Y %s\n' "$local_ssh_target" >&2
  cat >&2 <<'EOF'

Then run this script again on the Jetson host.
EOF
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  echo "Container '${CONTAINER_NAME}' is not running. Start it first:" >&2
  echo "  cd ~/ROS2/xarm_ws && bash scripts/run_jetson_container.sh" >&2
  exit 1
fi

if command -v xauth >/dev/null 2>&1; then
  touch "${XAUTH_FILE}"
  chmod 600 "${XAUTH_FILE}"
  # Convert the current SSH-forwarded cookie into a form readable inside Docker.
  if xauth nlist "${DISPLAY}" 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f "${XAUTH_FILE}" nmerge - 2>/dev/null; then
    chmod 644 "${XAUTH_FILE}"
    docker cp "${XAUTH_FILE}" "${CONTAINER_NAME}:${CONTAINER_XAUTH}" >/dev/null
    docker exec -it \
      -e DISPLAY="${DISPLAY}" \
      -e XAUTHORITY="${CONTAINER_XAUTH}" \
      -e QT_X11_NO_MITSHM=1 \
      "${CONTAINER_NAME}" bash
    exit $?
  fi
fi

echo "Warning: xauth cookie setup failed; trying DISPLAY passthrough without XAUTHORITY." >&2
docker exec -it \
  -e DISPLAY="${DISPLAY}" \
  -e QT_X11_NO_MITSHM=1 \
  "${CONTAINER_NAME}" bash
