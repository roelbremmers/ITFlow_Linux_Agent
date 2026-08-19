from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_systemd_service_runs_as_root_and_keeps_hardening():
    unit = (ROOT / "systemd/itflow-agent.service").read_text(encoding="utf-8")

    assert "User=root" in unit
    assert "Group=root" in unit
    for directive in (
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "ProtectSystem=strict",
        "ProtectHome=yes",
        "ProtectKernelTunables=yes",
        "ProtectKernelModules=yes",
        "ProtectControlGroups=yes",
        "RestrictSUIDSGID=yes",
        "LockPersonality=yes",
        "RestrictRealtime=yes",
        "SystemCallArchitectures=native",
    ):
        assert directive in unit


def test_installer_uses_root_without_creating_service_account():
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "useradd" not in installer
    assert "groupadd" not in installer
    assert 'install -d -m 0750 -o root -g root "$CONFIG_DIR"' in installer
    assert (
        'install -m 0640 -o root -g root '
        '"$PROJECT_DIR/config/config.toml.example" "$CONFIG_DIR/config.toml"'
        in installer
    )
