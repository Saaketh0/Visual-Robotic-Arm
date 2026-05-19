from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            Node(package="xarm_runtime", executable="synthetic_pixel_error_publisher", output="screen"),
            Node(package="xarm_runtime", executable="servo_controller_node", output="screen"),
            Node(package="xarm_gazebo_sim", executable="gazebo_backend_node", output="screen"),
        ]
    )
