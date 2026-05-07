#!/usr/bin/env zsh

set -e

echo "Starting clean xArm Gazebo world..."

# Paths
XARM_REPO="$HOME/ROS2/xarm_ws/src/xArm_Lewansoul_ROS"
XARM_SDF="$HOME/ROS2/xarm_ws/src/xarm_1s_description/urdf/xarm_mesh_control.sdf"
WORLD_NAME="empty"
MODEL_NAME="xarm_mesh"

# Check files
if [ ! -d "$XARM_REPO" ]; then
  echo "ERROR: Missing mesh repo:"
  echo "$XARM_REPO"
  exit 1
fi

if [ ! -f "$XARM_SDF" ]; then
  echo "ERROR: Missing xArm SDF:"
  echo "$XARM_SDF"
  exit 1
fi

# Kill old Gazebo processes
echo "Stopping old Gazebo processes..."
pkill -f "gz sim" 2>/dev/null || true
pkill -f "gz-gui" 2>/dev/null || true
pkill -f "gzserver" 2>/dev/null || true

sleep 2

# Make Gazebo able to find model://xarm_description/...
export GZ_SIM_RESOURCE_PATH="$GZ_SIM_RESOURCE_PATH:$XARM_REPO"

echo "GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH"

# Start Gazebo
echo "Opening Gazebo empty world..."
gz sim empty.sdf &

GZ_PID=$!

# Wait for Gazebo create service
echo "Waiting for Gazebo world service..."
for i in {1..30}; do
  if gz service -l 2>/dev/null | grep -q "/world/$WORLD_NAME/create"; then
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
gz service -s /world/$WORLD_NAME/create \
  --reqtype gz.msgs.EntityFactory \
  --reptype gz.msgs.Boolean \
  --timeout 3000 \
  --req "sdf_filename: \"$XARM_SDF\", name: \"$MODEL_NAME\", pose: {position: {x: 0, y: 0, z: 0.02}}"

echo "Done Initializing"

wait $GZ_PID
