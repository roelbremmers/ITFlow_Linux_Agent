import pytest

from itflow_agent.errors import IdentityError
from itflow_agent.identity import normalize_serial


def test_normalizes_serial_whitespace():
    assert normalize_serial("  ABC\n 123  ") == "ABC 123"


@pytest.mark.parametrize("value", ["", "0", "Unknown", "To Be Filled By O.E.M.", "00"])
def test_rejects_unsafe_serials(value):
    with pytest.raises(IdentityError):
        normalize_serial(value)

