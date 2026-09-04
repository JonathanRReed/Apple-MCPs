import pytest

from apple_mcp_common.runtime import require_loopback_host


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.42.0.9", "::1"])
def test_require_loopback_host_accepts_local_addresses(host: str) -> None:
    assert require_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.2", "example.com", ""])
def test_require_loopback_host_rejects_network_exposure(host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        require_loopback_host(host)
