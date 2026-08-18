from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config
from .errors import APIError

LOG = logging.getLogger(__name__)


class ITFlowClient:
    def __init__(self, config: Config, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        if session is None:
            retries = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=1,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),
            )
            self.session.mount("https://", HTTPAdapter(max_retries=retries))
            self.session.mount("http://", HTTPAdapter(max_retries=retries))

    def _call(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url}/api/v1/{endpoint}"
        parameters = {"api_key": self.config.api_key, **(params or {})}
        body = {"api_key": self.config.api_key, **(payload or {})} if payload is not None else None
        LOG.debug("ITFlow request method=%s endpoint=%s", method, endpoint)
        try:
            response = self.session.request(
                method,
                url,
                params=parameters if method.upper() == "GET" else None,
                json=body,
                timeout=self.config.request_timeout_seconds,
                verify=self.config.verify_tls,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise APIError(f"ITFlow request failed for {endpoint}: {exc}") from exc
        if not isinstance(data, dict):
            raise APIError(f"ITFlow returned a non-object response for {endpoint}")

        success = str(data.get("success", "")).casefold() == "true"
        message = str(data.get("message", ""))
        if not success:
            if "no resource" in message.casefold():
                return {"success": True, "count": 0, "data": [], "message": message}
            raise APIError(f"ITFlow rejected {endpoint}: {message or 'success=false'}")
        return data

    def probe(self) -> None:
        self._call("GET", "assets/read.php", params={"limit": 1})

    def find_assets_by_serial(self, serial: str, client_id: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"asset_serial": serial}
        if client_id is not None:
            params["client_id"] = client_id
        response = self._call("GET", "assets/read.php", params=params)
        data = response.get("data", [])
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def create_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", "assets/create.php", payload=payload)

    def update_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", "assets/update.php", payload=payload)

    def create_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._call("POST", "tickets/create.php", payload=payload)
        except APIError:
            if "ticket_asset_id" not in payload:
                raise
            fallback = dict(payload)
            fallback.pop("ticket_asset_id")
            LOG.warning("Ticket asset linking was rejected; retrying without ticket_asset_id")
            return self._call("POST", "tickets/create.php", payload=fallback)
