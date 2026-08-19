#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root." >&2
    exit 1
fi

if [ ! -r /etc/os-release ] || ! grep -q '^ID=debian' /etc/os-release; then
    echo "This installer supports Debian 12 or newer." >&2
    exit 1
fi
. /etc/os-release
if [ "${VERSION_ID%%.*}" -lt 12 ]; then
    echo "Debian 12 or newer is required (Python 3.11+)." >&2
    exit 1
fi

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INSTALL_DIR=/opt/itflow-agent
CONFIG_DIR=/etc/itflow-agent
UNIT_DIR=/etc/systemd/system

apt-get update
apt-get install -y python3 python3-venv python3-pip iproute2 util-linux

install -d -m 0755 "$INSTALL_DIR"
cp -R "$PROJECT_DIR/itflow_agent" "$PROJECT_DIR/pyproject.toml" "$PROJECT_DIR/README.md" "$INSTALL_DIR/"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --disable-pip-version-check --no-cache-dir "$INSTALL_DIR"

install -d -m 0750 -o root -g root "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
    install -m 0640 -o root -g root "$PROJECT_DIR/config/config.toml.example" "$CONFIG_DIR/config.toml"
fi
if [ ! -f "$CONFIG_DIR/api-key" ]; then
    umask 077
    : > "$CONFIG_DIR/api-key"
    chown root:root "$CONFIG_DIR/api-key"
    echo "Created empty $CONFIG_DIR/api-key; insert the ITFlow API key before starting the service."
fi

install -m 0644 "$PROJECT_DIR/systemd/itflow-agent.service" "$UNIT_DIR/itflow-agent.service"
install -m 0644 "$PROJECT_DIR/systemd/itflow-agent.timer" "$UNIT_DIR/itflow-agent.timer"
systemctl daemon-reload
systemctl enable itflow-agent.timer

echo "Installation complete."
echo "1. Edit $CONFIG_DIR/config.toml"
echo "2. Put the API key in $CONFIG_DIR/api-key and keep mode 0600"
echo "3. Test: systemctl start itflow-agent.service"
echo "4. Enable schedule now: systemctl start itflow-agent.timer"
