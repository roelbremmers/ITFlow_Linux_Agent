from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .api import ITFlowClient
from .config import load_config
from .errors import APIError, AmbiguousMatchError, ConfigurationError, IdentityError, InventoryError
from .inventory import collect_inventory
from .state import atomic_write_json, load_state
from .sync import SyncEngine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize this Linux host with ITFlow")
    parser.add_argument("--config", type=Path, default=Path("/etc/itflow-agent/config.toml"))
    parser.add_argument("--test", "--dry-run", dest="dry_run", action="store_true", help="collect and query, but do not POST or modify local state")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s event=%(message)s", stream=sys.stdout)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _logging(args.verbose)
    log = logging.getLogger("itflow_agent")
    try:
        config = load_config(args.config)
        inventory = collect_inventory()
        state = load_state(config.state_file)
        result = SyncEngine(config, ITFlowClient(config)).run(inventory, state, dry_run=args.dry_run)
        if not args.dry_run:
            new_state = dict(state)
            new_state.update({
                "last_success": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "last_sent_ip": inventory.ip,
                "last_sent_mac": inventory.mac,
                "last_asset_id": result.asset_id,
                "last_client_id": result.client_id,
            })
            if result.transfer_followed and config.persist_followed_client:
                new_state["followed_client_id"] = result.client_id
            atomic_write_json(config.snapshot_file, inventory.snapshot())
            atomic_write_json(config.state_file, new_state)
        log.info("sync_complete action=%s asset_id=%s client_id=%s changed_fields=%s dry_run=%s", result.action, result.asset_id, result.client_id, ",".join(result.changed_fields), args.dry_run)
        return 0
    except (ConfigurationError, IdentityError) as exc:
        log.error("configuration_or_identity_error detail=%s", exc)
        return 2
    except AmbiguousMatchError as exc:
        log.error("ambiguous_match detail=%s", exc)
        return 4
    except APIError as exc:
        log.error("api_error detail=%s", exc)
        return 3
    except InventoryError as exc:
        log.error("inventory_error detail=%s", exc)
        return 5
    except Exception:
        log.exception("unexpected_error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

