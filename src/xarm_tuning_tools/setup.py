from setuptools import find_packages, setup


package_name = "xarm_tuning_tools"


setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="user",
    maintainer_email="saaketh1001@gmail.com",
    description="Detachable tuning utilities for the xArm visual servo stack.",
    license="UNLICENSED",
    entry_points={
        "console_scripts": [
            "synthetic_pixel_error_publisher = xarm_tuning_tools.synthetic_pixel_error_publisher:main",
        ],
    },
)
