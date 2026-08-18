import json
from pathlib import Path

from itflow_agent.inventory import collect_inventory


def test_collects_linux_inventory(tmp_path: Path):
    dmi = tmp_path / "sys/class/dmi/id"
    net = tmp_path / "sys/class/net/eth0"
    proc = tmp_path / "proc"
    etc = tmp_path / "etc"
    dmi.mkdir(parents=True)
    net.mkdir(parents=True)
    proc.mkdir()
    etc.mkdir()
    (dmi / "product_serial").write_text("ABC123\n", encoding="utf-8")
    (dmi / "sys_vendor").write_text("Dell Inc.\n", encoding="utf-8")
    (dmi / "product_name").write_text("PowerEdge R640\n", encoding="utf-8")
    (dmi / "chassis_type").write_text("23\n", encoding="utf-8")
    (net / "address").write_text("aa:bb:cc:dd:ee:ff\n", encoding="utf-8")
    (proc / "cpuinfo").write_text("processor: 0\nmodel name: Test CPU\nprocessor: 1\n", encoding="utf-8")
    (proc / "meminfo").write_text("MemTotal:       1048576 kB\n", encoding="utf-8")
    (etc / "os-release").write_text('PRETTY_NAME="Debian GNU/Linux 13"\n', encoding="utf-8")

    def runner(command):
        if command[0] == "systemd-detect-virt":
            return "none\n"
        if command[0] == "lsblk":
            return json.dumps({"blockdevices": [{"name": "sda", "type": "disk"}]})
        if "route" in command:
            return json.dumps([{"dev": "eth0", "metric": 100}])
        if "address" in command:
            return json.dumps([{
                "ifname": "eth0", "operstate": "UP", "address": "aa:bb:cc:dd:ee:ff",
                "addr_info": [{"local": "192.0.2.10", "scope": "global"}],
            }])
        raise AssertionError(command)

    result = collect_inventory(tmp_path, runner)
    assert result.serial == "ABC123"
    assert result.asset_type == "Server"
    assert result.ip == "192.0.2.10"
    assert result.mac == "AA:BB:CC:DD:EE:FF"
    assert result.memory["total_gb"] == 1.0
