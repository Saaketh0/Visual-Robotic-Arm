from setuptools import find_packages, setup

package_name = "xarm_gazebo_sim"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(where="src", exclude=["test"]),
    package_dir={"": "src"},
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
(f"share/{package_name}/launch", ["launch/sim.launch.py", "launch/tuning.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="saake",
    maintainer_email="saaketh1001@gmail.com",
    description="Development-only Gazebo wiring for the xArm ROS2 stack.",
    license="UNLICENSED",
    entry_points={
        "console_scripts": [
            "gazebo_backend_node = xarm_gazebo_sim.gazebo_backend_node:main",
        ]
    },
)
