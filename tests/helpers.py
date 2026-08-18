from __future__ import annotations

from pathlib import Path

from itflow_agent.config import Config
from itflow_agent.models import Inventory


def config(tmp_path: Path, **overrides) -> Config:
    values = {
        "base_url": "https://itflow.example",
        "client_id": 11,
        "api_key": "secret",
        "state_dir": tmp_path,
    }
    values.update(overrides)
    return Config(**values)


def inventory() -> Inventory:
    return Inventory(
        serial="ABC123",
        hostname="debian-01",
        make="Dell Inc.",
        model="PowerEdge R640",
        os="Debian GNU/Linux 13",
        mac="AA:BB:CC:DD:EE:FF",
        ip="192.0.2.10",
        asset_type="Server",
        cpu={"model": "Example CPU", "logical_processors": 8},
        memory={"total_gb": 16.0},
    )


class FakeClient:
    def __init__(self, local=None, global_matches=None):
        self.local = [] if local is None else local
        self.global_matches = [] if global_matches is None else global_matches
        self.calls = []

    def probe(self):
        self.calls.append(("probe",))

    def find_assets_by_serial(self, serial, client_id=None):
        self.calls.append(("find", serial, client_id))
        return self.local if client_id is not None else self.global_matches

    def create_asset(self, payload):
        self.calls.append(("create", payload))
        return {"success": True, "data": [{"insert_id": 99}]}

    def update_asset(self, payload):
        self.calls.append(("update", payload))
        return {"success": True}

    def create_ticket(self, payload):
        self.calls.append(("ticket", payload))
        return {"success": True}

