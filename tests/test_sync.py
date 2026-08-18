import pytest

from itflow_agent.errors import AmbiguousMatchError
from itflow_agent.sync import SyncEngine

from .helpers import FakeClient, config, inventory


def test_creates_when_serial_does_not_exist(tmp_path):
    client = FakeClient()
    result = SyncEngine(config(tmp_path), client).run(inventory(), {})
    assert result.action == "create"
    assert result.asset_id == 99
    assert any(call[0] == "create" for call in client.calls)
    assert any(call[0] == "ticket" for call in client.calls)


def test_dry_run_never_posts(tmp_path):
    client = FakeClient()
    result = SyncEngine(config(tmp_path), client).run(inventory(), {}, dry_run=True)
    assert result.dry_run is True
    assert {call[0] for call in client.calls} <= {"probe", "find"}


def test_updates_matched_asset(tmp_path):
    asset = {
        "asset_id": 42,
        "asset_client_id": 11,
        "asset_name": "debian-01",
        "asset_status": "Archived",
        "asset_type": "Other",
        "asset_os": "Old OS",
        "asset_make": "Dell Inc.",
        "asset_model": "PowerEdge R640",
    }
    client = FakeClient(local=[asset])
    result = SyncEngine(config(tmp_path), client).run(inventory(), {})
    update = next(call[1] for call in client.calls if call[0] == "update")
    assert result.asset_id == 42
    assert update["asset_status"] == "Deployed"
    assert update["asset_type"] == "Server"
    assert update["asset_os"] == "Debian GNU/Linux 13"
    assert "asset_description" in update


def test_follows_transfer_and_updates_same_run(tmp_path):
    moved = {
        "asset_id": 55,
        "asset_client_id": 22,
        "asset_name": "debian-01",
        "asset_status": "Deployed",
        "asset_type": "Server",
        "asset_os": "Debian GNU/Linux 13",
        "asset_make": "Dell Inc.",
        "asset_model": "PowerEdge R640",
    }
    client = FakeClient(global_matches=[moved])
    result = SyncEngine(config(tmp_path), client).run(inventory(), {})
    assert result.transfer_followed is True
    assert result.client_id == 22
    update = next(call[1] for call in client.calls if call[0] == "update")
    assert update["client_id"] == 22
    assert len([call for call in client.calls if call[0] == "ticket"]) == 2


def test_refuses_ambiguous_global_match(tmp_path):
    client = FakeClient(global_matches=[{"asset_id": 1}, {"asset_id": 2}])
    with pytest.raises(AmbiguousMatchError):
        SyncEngine(config(tmp_path), client).run(inventory(), {})
    assert not any(call[0] in {"create", "update", "ticket"} for call in client.calls)

