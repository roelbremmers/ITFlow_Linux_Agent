from __future__ import annotations

import re

from .errors import IdentityError


INVALID_SERIALS = {
    "0",
    "00000000",
    "default string",
    "none",
    "not applicable",
    "not specified",
    "system serial number",
    "to be filled by o.e.m.",
    "unknown",
}


def normalize_serial(value: str) -> str:
    serial = re.sub(r"\s+", " ", value.replace("\x00", "")).strip()
    if len(serial) < 3 or serial.casefold() in INVALID_SERIALS:
        raise IdentityError(f"Unsafe or missing hardware serial: {serial!r}")
    if len(serial) > 255:
        raise IdentityError("Hardware serial is longer than 255 characters")
    return serial
