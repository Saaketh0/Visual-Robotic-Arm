from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            SetEnvironmentVariable("INFERENCE_BACKEND", "ultralytics"),
            SetEnvironmentVariable("ENABLE_IMSHOW", "true"),
            SetEnvironmentVariable("ENABLE_UDP_PREVIEW", "false"),
            Node(package="xarm_runtime", executable="tracker_node", arguments=["--sim"], output="screen"),
            Node(package="xarm_runtime", executable="servo_controller_node", output="screen"),
            Node(package="xarm_gazebo_sim", executable="gazebo_backend_node", output="screen"),
        ]
    )
