from pathlib import Path

import pytest

from apple_mcp_common.atomic import rename_without_replacement


@pytest.mark.parametrize("invalid", ["source", "destination"])
def test_encoded_nul_is_rejected_before_loading_libc(monkeypatch, tmp_path, invalid):
    source, destination = tmp_path / "source", tmp_path / "destination"
    if invalid == "source":
        source = Path(str(source) + "\0suffix")
    else:
        destination = Path(str(destination) + "\0suffix")

    def forbidden(*args, **kwargs):
        raise AssertionError("NUL input reached native code")

    monkeypatch.setattr("apple_mcp_common.atomic.ctypes.CDLL", forbidden)
    with pytest.raises(ValueError, match="NUL"):
        rename_without_replacement(source, destination)
