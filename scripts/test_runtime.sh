#!/usr/bin/env bash
# Note: we intentionally avoid `set -u` because ROS2/colcon setup scripts
# may reference unset variables (e.g. COLCON_TRACE) and `nounset` would abort.
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f install/setup.bash ]; then
  echo "install/setup.bash not found. Build first:"
  echo "  colcon build --packages-select xarm_runtime xarm_1s_description xarm_tuning_tools"
  exit 1
fi

# Some ROS2 Python environments auto-install incompatible pytest plugins.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

source install/setup.bash
pytest -q src/xarm_runtime/test
