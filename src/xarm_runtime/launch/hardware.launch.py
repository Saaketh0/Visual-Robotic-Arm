from pathlib import Path

from launch import LaunchDescription
from launch_ros.actions import Node

try:
    from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
except ImportError:  # pragma: no cover - import guard for direct source-tree tests
    PackageNotFoundError = Exception
    get_package_share_directory = None


def package_file(relative_path: str) -> str:
    if get_package_share_directory is not None:
        try:
            return str(Path(get_package_share_directory("xarm_runtime")) / relative_path)
        except PackageNotFoundError:
            pass
    return str(Path(__file__).resolve().parents[1] / relative_path)


def generate_launch_description() -> LaunchDescription:
    jetson_config = package_file("config/jetson.yaml")
    return LaunchDescription(
        [
            Node(package="xarm_runtime", executable="tracker_node", output="screen", parameters=[jetson_config]),
            Node(package="xarm_runtime", executable="servo_controller_node", output="screen"),
            Node(package="xarm_runtime", executable="device_backend_node", output="screen", parameters=[jetson_config]),
        ]
    )
