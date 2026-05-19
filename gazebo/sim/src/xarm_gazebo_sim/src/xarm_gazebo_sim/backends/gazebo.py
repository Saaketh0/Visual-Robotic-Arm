from __future__ import annotations

import os
import subprocess
from typing import Callable, Iterable, Tuple

from xarm_runtime.joint_model import JOINT_ORDER, JOINTS

# Development-only helper. Do not assume Homebrew paths.
# - On Linux containers/Jetson: usually `gz` is on PATH.
# - On macOS: export GZ_BIN=/opt/homebrew/bin/gz (or wherever gz is installed).
GZ_BIN = os.environ.get("GZ_BIN", "gz")

TopicSender = Callable[[str, float], None]


def topic_pairs() -> Tuple[Tuple[str, str], ...]:
    return tuple((name, JOINTS[name]["topic"]) for name in JOINT_ORDER)


def sanitized_gz_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Run gz with a minimal env so host Python/Conda/Homebrew library vars don't leak in."""

    env = base_env or os.environ
    keep_path = env.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    return {
        "HOME": env.get("HOME", os.getcwd()),
        "USER": env.get("USER", ""),
        "LOGNAME": env.get("LOGNAME", env.get("USER", "")),
        "SHELL": env.get("SHELL", "/bin/bash"),
        "TMPDIR": env.get("TMPDIR", "/tmp"),
        "TERM": env.get("TERM", "xterm-256color"),
        "LANG": env.get("LANG", "en_US.UTF-8"),
        "LC_ALL": env.get("LC_ALL", "en_US.UTF-8"),
        "PATH": keep_path,
    }


def send_gz_double(topic: str, value: float, gz_bin: str = GZ_BIN) -> None:
    subprocess.run(
        [gz_bin, "topic", "-t", topic, "-m", "gz.msgs.Double", "-p", f"data: {float(value)}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=sanitized_gz_env(),
    )


def forward_joint_cmds(values: Iterable[float], topic_sender: TopicSender = send_gz_double) -> None:
    for (_, topic), value in zip(topic_pairs(), values):
        topic_sender(topic, float(value))
