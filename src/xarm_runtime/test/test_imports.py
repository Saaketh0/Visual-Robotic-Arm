from importlib import import_module


MODULES = [
    "xarm_runtime",
    "xarm_runtime.joint_model",
    "xarm_runtime.tracker_config",
    "xarm_runtime.tracker_node",
    "xarm_runtime.servo_controller_node",
    "xarm_runtime.device_backend_node",
    "xarm_runtime.synthetic_pixel_error_publisher",
    "xarm_runtime.backends.serial_device",
]


def test_runtime_modules_import() -> None:
    for module_name in MODULES:
        import_module(module_name)
