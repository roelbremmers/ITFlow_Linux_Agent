from unittest.mock import Mock

import pytest

from itflow_agent.api import ITFlowClient
from itflow_agent.errors import APIError

from .helpers import config


def response(payload, status_error=None):
    result = Mock()
    result.raise_for_status.side_effect = status_error
    result.json.return_value = payload
    return result


def test_get_uses_encoded_params_and_parses_assets(tmp_path):
    session = Mock()
    session.request.return_value = response({"success": True, "data": [{"asset_id": 3}]})
    client = ITFlowClient(config(tmp_path), session=session)
    assert client.find_assets_by_serial("ABC 123", 11)[0]["asset_id"] == 3
    kwargs = session.request.call_args.kwargs
    assert kwargs["params"] == {"api_key": "secret", "asset_serial": "ABC 123", "client_id": 11}


def test_no_resource_becomes_empty_result(tmp_path):
    session = Mock()
    session.request.return_value = response({"success": False, "message": "No resource"})
    assert ITFlowClient(config(tmp_path), session=session).find_assets_by_serial("ABC123") == []


def test_other_api_failure_raises(tmp_path):
    session = Mock()
    session.request.return_value = response({"success": False, "message": "Denied"})
    with pytest.raises(APIError):
        ITFlowClient(config(tmp_path), session=session).probe()


def test_ticket_retries_without_asset_link(tmp_path):
    session = Mock()
    session.request.side_effect = [
        response({"success": False, "message": "Unknown field ticket_asset_id"}),
        response({"success": True}),
    ]
    client = ITFlowClient(config(tmp_path), session=session)
    client.create_ticket({"client_id": 11, "ticket_subject": "Test", "ticket_asset_id": 9})
    second_payload = session.request.call_args_list[1].kwargs["json"]
    assert "ticket_asset_id" not in second_payload

