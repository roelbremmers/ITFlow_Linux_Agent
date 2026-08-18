from pathlib import Path

import pytest

from itflow_agent.config import load_config
from itflow_agent.errors import ConfigurationError


def test_loads_key_from_systemd_credential(tmp_path: Path):
    credential_dir = tmp_path / "credentials"
    credential_dir.mkdir()
    (credential_dir / "itflow_api_key").write_text("top-secret\n", encoding="utf-8")
    config_file = tmp_path / "config.toml"
    config_file.write_text('base_url="https://itflow.example"\nclient_id=11\n', encoding="utf-8")
    result = load_config(config_file, {"CREDENTIALS_DIRECTORY": str(credential_dir)})
    assert result.api_key == "top-secret"
    assert result.client_id == 11


def test_rejects_invalid_client(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('base_url="https://itflow.example"\nclient_id=0\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(config_file, {"ITFLOW_API_KEY": "secret"})

