from __future__ import annotations

import re
import uuid

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


def normalize_product_uuid(value: str) -> str:
    """Return a DMI UUID in the same canonical form commonly reported by WMI."""
    candidate = value.replace("\x00", "").strip()
    try:
        product_uuid = uuid.UUID(candidate)
    except (ValueError, AttributeError):
        raise IdentityError(f"Unsafe or missing hardware UUID: {candidate!r}") from None
    if product_uuid.int in {0, (1 << 128) - 1}:
        raise IdentityError(f"Unsafe or missing hardware UUID: {candidate!r}")
    return str(product_uuid).upper()


def select_hardware_serial(product_serial: str, product_uuid: str) -> str:
    """Prefer a usable DMI serial, falling back to the product UUID."""
    try:
        return normalize_serial(product_serial)
    except IdentityError:
        return normalize_product_uuid(product_uuid)
