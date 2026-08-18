from itflow_agent.state import atomic_write_json, load_state


def test_atomic_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    atomic_write_json(path, {"last_asset_id": 42})
    assert load_state(path) == {"last_asset_id": 42}


def test_invalid_state_is_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json", encoding="utf-8")
    assert load_state(path) == {}

