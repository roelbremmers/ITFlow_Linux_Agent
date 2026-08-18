from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable

from .errors import InventoryError
from .identity import normalize_serial
from .models import Inventory

Runner = Callable[[list[str]], str]


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=15
    )
    return completed.stdout


def _text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def _os_name(root: Path) -> str:
    values: dict[str, str] = {}
    for line in _text(root / "etc/os-release").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values.get("PRETTY_NAME") or platform.platform()


def _cpu(root: Path) -> dict[str, Any]:
    model = ""
    logical = 0
    for line in _text(root / "proc/cpuinfo").splitlines():
        if line.startswith("processor"):
            logical += 1
        elif not model and line.lower().startswith(("model name", "hardware")):
            model = line.split(":", 1)[-1].strip()
    return {"model": model or platform.processor(), "logical_processors": logical or os.cpu_count()}


def _memory(root: Path) -> dict[str, Any]:
    for line in _text(root / "proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            kib = int(line.split()[1])
            return {"total_bytes": kib * 1024, "total_gb": round(kib / 1024 / 1024, 2)}
    return {}


def _json_command(runner: Runner, command: list[str], key: str) -> list[dict[str, Any]]:
    try:
        result = json.loads(runner(command))
        value = result.get(key, [])
        return value if isinstance(value, list) else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, AttributeError):
        return []


def _primary_network(
    root: Path, runner: Runner
) -> tuple[str, str, list[dict[str, Any]]]:
    routes = _json_command(runner, ["ip", "-json", "-4", "route", "show", "default"], "unused")
    # ip emits a top-level JSON array rather than an object.
    try:
        parsed = json.loads(runner(["ip", "-json", "-4", "route", "show", "default"]))
        routes = parsed if isinstance(parsed, list) else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        routes = []
    routes.sort(key=lambda item: int(item.get("metric", 0)))
    interface = str(routes[0].get("dev", "")) if routes else ""

    addresses: list[dict[str, Any]] = []
    try:
        parsed = json.loads(runner(["ip", "-json", "address", "show"]))
        addresses = parsed if isinstance(parsed, list) else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    primary_ip = ""
    network: list[dict[str, Any]] = []
    for adapter in addresses:
        name = str(adapter.get("ifname", ""))
        addr_info = adapter.get("addr_info", [])
        ips = [
            str(addr.get("local", ""))
            for addr in addr_info
            if addr.get("scope") == "global" and addr.get("local")
        ]
        mac = str(adapter.get("address", "")).upper()
        network.append(
            {
                "name": name,
                "status": str(adapter.get("operstate", "unknown")),
                "mac": mac,
                "addresses": ips,
            }
        )
        if name == interface:
            ipv4 = next((ip for ip in ips if ":" not in ip), "")
            primary_ip = ipv4

    primary_mac = _text(root / f"sys/class/net/{interface}/address").upper() if interface else ""
    if not primary_mac:
        primary_mac = next((n["mac"] for n in network if n["name"] == interface), "")
    return primary_ip, primary_mac, network


def _asset_type(root: Path, make: str, model: str, runner: Runner) -> str:
    try:
        virtualization = runner(["systemd-detect-virt"]).strip()
        if virtualization and virtualization != "none":
            return "Virtual Machine"
    except (OSError, subprocess.SubprocessError):
        pass

    chassis = _text(root / "sys/class/dmi/id/chassis_type")
    try:
        chassis_number = int(chassis)
    except ValueError:
        chassis_number = 0
    if chassis_number in {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}:
        return "Laptop"
    if chassis_number in {3, 4, 5, 6, 7, 15, 16, 35, 36}:
        return "Desktop"
    lowered = f"{make} {model}".casefold()
    if any(word in lowered for word in ("server", "poweredge", "proliant", "thinksystem")):
        return "Server"
    return "Other"


def collect_inventory(root: Path = Path("/"), runner: Runner = _run) -> Inventory:
    dmi = root / "sys/class/dmi/id"
    serial = normalize_serial(_text(dmi / "product_serial"))
    make = _text(dmi / "sys_vendor")
    model = _text(dmi / "product_name")
    hostname = socket.gethostname().strip()
    if not hostname:
        raise InventoryError("Hostname is empty")

    ip, mac, network = _primary_network(root, runner)
    storage = _json_command(
        runner,
        ["lsblk", "--json", "--bytes", "--output", "NAME,TYPE,SIZE,MODEL,SERIAL,ROTA,FSTYPE,MOUNTPOINTS"],
        "blockdevices",
    )
    return Inventory(
        serial=serial,
        hostname=hostname,
        make=make,
        model=model,
        os=_os_name(root),
        mac=mac,
        ip=ip,
        asset_type=_asset_type(root, make, model, runner),
        cpu=_cpu(root),
        memory=_memory(root),
        storage=storage,
        network=network,
    )
