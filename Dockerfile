# Build/test/dev container only. This is not the supported live camera + serial
# runtime path for Jetson Nano phase 1.
FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace/xarm_ws

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    python3-pip \
    python3-pytest \
    python3-opencv \
    python3-serial \
    python3-dotenv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-jetson.txt /tmp/requirements-jetson.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-jetson.txt

COPY src ./src
COPY README.md ./README.md
COPY docs ./docs

RUN . /opt/ros/humble/setup.sh \
    && colcon build --packages-select xarm_runtime xarm_1s_description xarm_tuning_tools

CMD ["bash", "-lc", ". /opt/ros/humble/setup.bash && . install/setup.bash && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q src/xarm_runtime/test"]
