from xarm_gazebo_sim.backends.gazebo import forward_joint_cmds, sanitized_gz_env, topic_pairs


def test_topic_pairs_follow_joint_order() -> None:
    assert [name for name, _ in topic_pairs()] == ["base", "shoulder", "elbow", "camera"]


def test_forward_joint_cmds_preserves_values_and_topics() -> None:
    sent = []
    forward_joint_cmds([0.1, 0.2, 0.3, 0.4], lambda topic, value: sent.append((topic, value)))
    assert sent == [
        ("/xarm/xarm_6_joint/cmd_pos", 0.1),
        ("/xarm/xarm_5_joint/cmd_pos", 0.2),
        ("/xarm/xarm_4_joint/cmd_pos", 0.3),
        ("/xarm/xarm_3_joint/cmd_pos", 0.4),
    ]


def test_sanitized_gz_env_drops_conda_and_rendering_paths() -> None:
    env = sanitized_gz_env(
        {
            "HOME": "/Users/test",
            "USER": "tester",
            "LOGNAME": "tester",
            "SHELL": "/bin/zsh",
            "TMPDIR": "/tmp/test",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "CONDA_PREFIX": "/conda/env",
            "IGN_RENDERING_RESOURCE_PATH": "/conda/ignition",
            "DYLD_LIBRARY_PATH": "/conda/lib",
            "PATH": "/conda/bin:/opt/homebrew/bin",
        }
    )

    assert env == {
        "HOME": "/Users/test",
        "USER": "tester",
        "LOGNAME": "tester",
        "SHELL": "/bin/zsh",
        "TMPDIR": "/tmp/test",
        "TERM": "xterm-256color",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    }
