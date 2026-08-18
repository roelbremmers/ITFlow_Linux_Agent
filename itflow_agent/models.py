from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Inventory:
    serial: str
    hostname: str
    make: str
    model: str
    os: str
    mac: str
    ip: str
    asset_type: str
    cpu: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    storage: list[dict[str, Any]] = field(default_factory=list)
    network: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SyncResult:
    action: str
    client_id: int
    asset_id: int | None = None
    changed_fields: tuple[str, ...] = ()
    transfer_followed: bool = False
    dry_run: bool = False

