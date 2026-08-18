from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigurationError


@dataclass(frozen=True)
class Config:
    base_url: str
    client_id: int
    api_key: str
    asset_status: str = "Deployed"
    follow_transfers: bool = True
    persist_followed_client: bool = False
    create_tickets: bool = True
    request_timeout_seconds: float = 30.0
    verify_tls: bool = True
    state_dir: Path = Path("/var/lib/itflow-agent")

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def snapshot_file(self) -> Path:
        return self.state_dir / "sysinfo.json"


def _read_secret(config: dict, environ: dict[str, str]) -> str:
    if environ.get("ITFLOW_API_KEY"):
        return environ["ITFLOW_API_KEY"].strip()

    credentials_dir = environ.get("CREDENTIALS_DIRECTORY")
    credential_name = str(config.get("api_key_credential", "itflow_api_key"))
    if credentials_dir:
        credential = Path(credentials_dir) / credential_name
        try:
            return credential.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(f"Cannot read systemd credential {credential_name!r}: {exc}") from exc

    secret_file = config.get("api_key_file")
    if secret_file:
        try:
            return Path(secret_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError(f"Cannot read api_key_file: {exc}") from exc

    raise ConfigurationError(
        "No API key available; use a systemd credential, ITFLOW_API_KEY, or api_key_file"
    )


def load_config(path: Path, environ: dict[str, str] | None = None) -> Config:
    environ = os.environ if environ is None else environ
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Cannot load configuration {path}: {exc}") from exc

    try:
        base_url = str(raw["base_url"]).rstrip("/")
        client_id = int(raw["client_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError("base_url and a positive integer client_id are required") from exc

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("base_url must be an absolute HTTP(S) URL")
    if client_id <= 0:
        raise ConfigurationError("client_id must be positive")

    api_key = _read_secret(raw, environ)
    if not api_key:
        raise ConfigurationError("API key is empty")

    timeout = float(raw.get("request_timeout_seconds", 30))
    if timeout <= 0:
        raise ConfigurationError("request_timeout_seconds must be positive")

    return Config(
        base_url=base_url,
        client_id=client_id,
        api_key=api_key,
        asset_status=str(raw.get("asset_status", "Deployed")),
        follow_transfers=bool(raw.get("follow_transfers", True)),
        persist_followed_client=bool(raw.get("persist_followed_client", False)),
        create_tickets=bool(raw.get("create_tickets", True)),
        request_timeout_seconds=timeout,
        verify_tls=bool(raw.get("verify_tls", True)),
        state_dir=Path(raw.get("state_dir", "/var/lib/itflow-agent")),
    )

