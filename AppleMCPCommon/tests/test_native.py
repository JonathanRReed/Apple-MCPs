import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from apple_mcp_common.native import NativeHelperError, ensure_swift_helper


def compile_fixture(monkeypatch, calls):
    def compile(command, **kwargs):
        assert kwargs["timeout"] == 300
        calls.append(command)
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", compile)


def test_legacy_cache_and_changed_source_with_older_mtime_recompile(monkeypatch, tmp_path):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("old")
    binary.write_text("legacy")
    calls = []
    compile_fixture(monkeypatch, calls)
    os.utime(source, (1, 1))
    os.utime(binary, (2, 2))
    assert ensure_swift_helper(source, binary)
    assert binary.read_text() == "old"
    assert not ensure_swift_helper(source, binary)
    source.write_text("fixed")
    os.utime(source, (1, 1))
    assert ensure_swift_helper(source, binary)
    assert binary.read_text() == "fixed"
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["error", "timeout", "source_changed"])
def test_failed_build_preserves_existing_executable_and_cache(monkeypatch, tmp_path, failure):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("new")
    binary.write_text("old")
    stamp = tmp_path / "helper.source.sha256"
    stamp.write_text("previous")

    def compile(command, **kwargs):
        Path(command[-1]).write_text("partial")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 300)
        if failure == "source_changed":
            source.write_text("changed again")
        return subprocess.CompletedProcess(command, 1 if failure == "error" else 0, stdout="", stderr="failed")

    monkeypatch.setattr(subprocess, "run", compile)
    with pytest.raises(NativeHelperError):
        ensure_swift_helper(source, binary)
    assert binary.read_text() == "old" and stamp.read_text() == "previous"
    assert not list(tmp_path.glob(".helper.*"))


def test_concurrent_builds_install_only_complete_binaries(monkeypatch, tmp_path):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("complete")
    calls = []
    compile_fixture(monkeypatch, calls)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: ensure_swift_helper(source, binary), range(4)))
    assert binary.read_text() == "complete"
    assert not ensure_swift_helper(source, binary)
    assert not list(tmp_path.glob(".helper.*"))
