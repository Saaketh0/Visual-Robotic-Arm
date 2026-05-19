from setuptools import find_packages, setup

package_name = "xarm_runtime"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(where="src", exclude=["test"]),
    package_dir={"": "src"},
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", [
            "launch/hardware.launch.py",
        ]),
        (f"share/{package_name}/config", [
            "config/hardware.yaml",
            "config/jetson.yaml",
            "config/sim.yaml",
        ]),
    ],
    install_requires=[
        "setuptools",
        "pyserial>=3.4,<4",
        "python-dotenv>=0.20,<1; python_version < '3.8'",
        "python-dotenv>=1.0,<2; python_version >= '3.8'",
        "dataclasses>=0.8,<1; python_version < '3.7'",
    ],
    zip_safe=True,
    maintainer="saake",
    maintainer_email="saaketh1001@gmail.com",
    description="Canonical ROS2 runtime package for xArm tracking and servo control.",
    license="UNLICENSED",
    entry_points={
        "console_scripts": [
            "tracker_node = xarm_runtime.tracker_node:main",
            "servo_controller_node = xarm_runtime.servo_controller_node:main",
            "device_backend_node = xarm_runtime.device_backend_node:main",
            "synthetic_pixel_error_publisher = xarm_runtime.synthetic_pixel_error_publisher:main",
        ],
    },
)
