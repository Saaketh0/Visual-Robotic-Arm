from xarm_runtime import ros_runtime


class _DummyNode:
    def __init__(self) -> None:
        self.destroy_calls = 0

    def destroy_node(self) -> None:
        self.destroy_calls += 1


def test_request_shutdown_skips_when_context_not_running(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(ros_runtime.rclpy, "ok", lambda: False)
    monkeypatch.setattr(ros_runtime.rclpy, "shutdown", lambda: calls.append("shutdown"))
    ros_runtime.request_shutdown()
    assert calls == []


def test_shutdown_node_destroys_then_shuts_down(monkeypatch) -> None:
    calls: list[str] = []
    node = _DummyNode()
    monkeypatch.setattr(ros_runtime.rclpy, "ok", lambda: True)
    monkeypatch.setattr(ros_runtime.rclpy, "shutdown", lambda: calls.append("shutdown"))
    ros_runtime.shutdown_node(node)
    assert node.destroy_calls == 1
    assert calls == ["shutdown"]


def test_shutdown_node_handles_missing_node(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(ros_runtime.rclpy, "ok", lambda: True)
    monkeypatch.setattr(ros_runtime.rclpy, "shutdown", lambda: calls.append("shutdown"))
    ros_runtime.shutdown_node(None)
    assert calls == ["shutdown"]
