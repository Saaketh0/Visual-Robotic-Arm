#!/usr/bin/env bash

set -euo pipefail

echo "Starting clean xArm Gazebo world..."

# Paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# This script assumes it's run from the repo root OR from within gazebo/sim.
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
XARM_SDF="$REPO_ROOT/src/xarm_1s_description/urdf/xarm_mesh_control.sdf"
WORLD_NAME="empty"
MODEL_NAME="xarm_mesh"
GZ_BIN="${GZ_BIN:-gz}"

# Keep env small so host Homebrew/Conda doesn't leak into gz via DYLD/LD vars.
gz_clean_env() {
  env -i \
    HOME="${HOME:-$REPO_ROOT}" \
    USER="${USER:-$(id -un)}" \
    LOGNAME="${LOGNAME:-${USER:-$(id -un)}}" \
    SHELL="${SHELL:-/bin/bash}" \
    TMPDIR="${TMPDIR:-/tmp}" \
    TERM="${TERM:-xterm-256color}" \
    LANG="${LANG:-en_US.UTF-8}" \
    LC_ALL="${LC_ALL:-en_US.UTF-8}" \
    PATH="${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}" \
    "$@"
}

# Check files
if [ ! -f "$XARM_SDF" ]; then
  echo "ERROR: Missing xArm SDF:"
  echo "$XARM_SDF"
  exit 1
fi

if ! command -v "$GZ_BIN" >/dev/null 2>&1; then
  echo "ERROR: Gazebo binary not found: $GZ_BIN"
  echo "Hint: export GZ_BIN=/path/to/gz"
  exit 1
fi

# Kill old Gazebo processes
echo "Stopping old Gazebo processes..."
pkill -f "gz sim" 2>/dev/null || true
pkill -f "gz-gui" 2>/dev/null || true
pkill -f "gzserver" 2>/dev/null || true

sleep 2

# Start Gazebo
echo "Opening Gazebo empty world..."
echo "Using Gazebo binary: $GZ_BIN"
echo "Launching Gazebo with sanitized dynamic-library environment..."
gz_clean_env "$GZ_BIN" sim empty.sdf &

GZ_PID=$!

# Wait for Gazebo create service
echo "Waiting for Gazebo world service..."
for i in $(seq 1 30); do
  if gz_clean_env "$GZ_BIN" service -l 2>/dev/null | grep -q "/world/$WORLD_NAME/create"; then
    echo "Gazebo is ready."
    break
  fi

  if [ "$i" -eq 30 ]; then
    echo "ERROR: Gazebo did not become ready."
    exit 1
  fi

  sleep 1
done

# Spawn xArm
echo "Spawning xArm model..."
gz_clean_env "$GZ_BIN" service -s "/world/$WORLD_NAME/create" \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --timeout 3000 \
  --req "sdf_filename: \"$XARM_SDF\", name: \"$MODEL_NAME\", pose: {position: {x: 0, y: 0, z: 0.02}}"

echo "Done initializing"

wait "$GZ_PID"
