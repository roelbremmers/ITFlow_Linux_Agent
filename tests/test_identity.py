import pytest

from itflow_agent.errors import IdentityError
from itflow_agent.identity import normalize_product_uuid, normalize_serial


def test_normalizes_serial_whitespace():
    assert normalize_serial("  ABC\n 123  ") == "ABC 123"


def test_accepts_vmware_serial_with_spaces():
    value = "VMware-42 13 1e f8 17 24 50 de-6c fc fe 72 c4 70 b0 db"
    assert normalize_serial(value) == value


@pytest.mark.parametrize("value", ["", "0", "Unknown", "To Be Filled By O.E.M.", "00"])
def test_rejects_unsafe_serials(value):
    with pytest.raises(IdentityError):
        normalize_serial(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "00000000-0000-0000-0000-000000000000",
        "ffffffff-ffff-ffff-ffff-ffffffffffff",
    ],
)
def test_rejects_unsafe_product_uuids(value):
    with pytest.raises(IdentityError):
        normalize_product_uuid(value)
