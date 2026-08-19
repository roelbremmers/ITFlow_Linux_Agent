from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any

from .api import ITFlowClient
from .config import Config
from .errors import AmbiguousMatchError, APIError
from .models import Inventory, SyncResult

LOG = logging.getLogger(__name__)


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


def _one_or_none(matches: list[dict[str, Any]], scope: str) -> dict[str, Any] | None:
    if len(matches) > 1:
        ids = [str(asset.get("asset_id", "?")) for asset in matches]
        raise AmbiguousMatchError(f"Multiple assets match the serial in {scope}: {', '.join(ids)}")
    return matches[0] if matches else None


def _asset_id(response: dict[str, Any]) -> int | None:
    data = response.get("data", [])
    if isinstance(data, list) and data:
        raw = data[0].get("insert_id") or data[0].get("asset_id")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return None


def _last_check_in() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _details(inventory: Inventory) -> str:
    return "\n".join(
        (
            f"Hostname: {inventory.hostname}",
            f"Serial: {inventory.serial}",
            f"Make/Model: {inventory.make} / {inventory.model}",
            f"OS: {inventory.os}",
            f"Type: {inventory.asset_type}",
            f"CPU: {inventory.cpu.get('model', '')}",
            f"Memory: {inventory.memory.get('total_gb', '')} GB",
            f"Primary MAC: {inventory.mac}",
            f"Primary IP: {inventory.ip}",
        )
    )


class SyncEngine:
    def __init__(self, config: Config, client: ITFlowClient):
        self.config = config
        self.client = client

    def _ticket(
        self, subject: str, client_id: int, inventory: Inventory, asset_id: int | None = None
    ) -> None:
        if not self.config.create_tickets:
            return
        payload: dict[str, Any] = {
            "client_id": client_id,
            "ticket_subject": subject,
            "ticket_details": html.escape(_details(inventory)).replace("\n", "<br>"),
        }
        if asset_id:
            payload["ticket_asset_id"] = asset_id
        try:
            self.client.create_ticket(payload)
        except APIError as exc:
            LOG.error("Ticket creation failed subject=%r error=%s", subject, exc)

    def _create(self, inventory: Inventory, client_id: int, dry_run: bool) -> SyncResult:
        fields = (
            "asset_name", "asset_serial", "asset_make", "asset_model", "asset_os",
            "asset_mac", "asset_ip", "asset_type", "asset_status", "asset_description",
        )
        if dry_run:
            LOG.info("DRY-RUN would create asset client_id=%s fields=%s", client_id, ",".join(fields))
            return SyncResult("create", client_id, changed_fields=fields, dry_run=True)
        response = self.client.create_asset(
            {
                "client_id": client_id,
                "asset_name": inventory.hostname,
                "asset_serial": inventory.serial,
                "asset_make": inventory.make,
                "asset_model": inventory.model,
                "asset_os": inventory.os,
                "asset_mac": inventory.mac,
                "asset_ip": inventory.ip,
                "asset_type": inventory.asset_type,
                "asset_status": self.config.asset_status,
                "asset_description": "Last Check-In: " + _last_check_in(),
            }
        )
        asset_id = _asset_id(response)
        self._ticket(
            f"[ENROLL] {inventory.hostname} | Serial: {inventory.serial} | {inventory.os}",
            client_id,
            inventory,
            asset_id,
        )
        return SyncResult("create", client_id, asset_id=asset_id, changed_fields=fields)

    def _update(
        self,
        inventory: Inventory,
        asset: dict[str, Any],
        client_id: int,
        state: dict[str, Any],
        dry_run: bool,
        transferred: bool,
    ) -> SyncResult:
        try:
            asset_id = int(asset["asset_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError("Matched asset has no valid asset_id") from exc

        desired = {
            "asset_status": self.config.asset_status,
            "asset_type": inventory.asset_type,
            "asset_os": inventory.os,
            "asset_make": inventory.make,
            "asset_model": inventory.model,
        }
        changes = {
            key: value
            for key, value in desired.items()
            if value and _normalized(asset.get(key)) != _normalized(value)
        }
        if not str(asset.get("asset_name", "")).strip():
            changes["asset_name"] = inventory.hostname

        if inventory.mac and _normalized(asset.get("asset_mac")) != _normalized(inventory.mac):
            changes["asset_mac"] = inventory.mac
        if inventory.ip and _normalized(asset.get("asset_ip")) != _normalized(inventory.ip):
            changes["asset_ip"] = inventory.ip
        changes["asset_description"] = "Last Check-In: " + _last_check_in()
        fields = tuple(sorted(changes))
        if dry_run:
            LOG.info("DRY-RUN would update asset_id=%s fields=%s", asset_id, ",".join(fields))
            return SyncResult("update", client_id, asset_id, fields, transferred, True)

        self.client.update_asset({"client_id": client_id, "asset_id": asset_id, **changes})
        return SyncResult("update", client_id, asset_id, fields, transferred)

    def run(
        self, inventory: Inventory, state: dict[str, Any], dry_run: bool = False
    ) -> SyncResult:
        configured_client = int(state.get("followed_client_id", self.config.client_id))
        self.client.probe()
        asset = _one_or_none(
            self.client.find_assets_by_serial(inventory.serial, configured_client),
            f"client {configured_client}",
        )
        transferred = False
        effective_client = configured_client

        if asset is None:
            global_asset = _one_or_none(
                self.client.find_assets_by_serial(inventory.serial), "all clients"
            )
            if global_asset is None:
                return self._create(inventory, effective_client, dry_run)
            try:
                discovered_client = int(global_asset["asset_client_id"])
                discovered_asset = int(global_asset["asset_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise APIError("Transferred asset lacks a valid client or asset id") from exc
            if not self.config.follow_transfers:
                raise APIError(
                    f"Serial exists as asset {discovered_asset} in client {discovered_client}; transfer following is disabled"
                )
            transferred = True
            asset = global_asset
            effective_client = discovered_client
            LOG.warning(
                "Transfer followed asset_id=%s old_client_id=%s new_client_id=%s",
                discovered_asset, configured_client, discovered_client,
            )
            if not dry_run:
                self._ticket(
                    f"[TRANSFER DETECTED] {inventory.hostname} | Serial: {inventory.serial} moved to client_id={discovered_client}",
                    configured_client,
                    inventory,
                )
                self._ticket(
                    f"[TRANSFER FOLLOWED] {inventory.hostname} | Serial: {inventory.serial} now in client_id={discovered_client}",
                    discovered_client,
                    inventory,
                    discovered_asset,
                )

        return self._update(
            inventory, asset, effective_client, state, dry_run, transferred
        )
