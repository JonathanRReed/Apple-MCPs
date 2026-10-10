import errno
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from apple_mcp_common.native import NativeHelperError, ensure_swift_helper, swift_helper_path


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
    old_path = ensure_swift_helper(source, binary)
    assert old_path.read_text() == "old"
    assert ensure_swift_helper(source, binary) == old_path
    source.write_text("fixed")
    os.utime(source, (1, 1))
    fixed_path = ensure_swift_helper(source, binary)
    assert fixed_path != old_path
    assert fixed_path.read_text() == "fixed"
    assert old_path.read_text() == "old"
    assert binary.read_text() == "legacy"
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
    assert not list(tmp_path.rglob(".*.swift"))
    assert not list(tmp_path.glob(".helper-*"))


def test_concurrent_builds_install_only_complete_binaries(monkeypatch, tmp_path):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("complete")
    calls = []
    compile_fixture(monkeypatch, calls)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: ensure_swift_helper(source, binary), range(4)))
    assert len(set(paths)) == 1
    assert paths[0].read_text() == "complete"
    assert ensure_swift_helper(source, binary) == paths[0]
    assert not list(tmp_path.rglob(".*.swift"))
    assert not list(tmp_path.glob(".helper-*"))


@pytest.mark.parametrize("app_bundle", [False, True])
@pytest.mark.parametrize("hard_link_errno", [None, *sorted({errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM})])
def test_distinct_source_versions_keep_their_returned_executables(monkeypatch, tmp_path, app_bundle, hard_link_errno):
    # Delay execution until BOTH versions have installed. A lock around a shared
    # binary + stamp cannot pass this: the returned shared path changes later.
    binary = tmp_path / "helper"
    if app_bundle:
        binary = tmp_path / "helper.app" / "Contents" / "MacOS" / "helper"
    sources = [tmp_path / "old.swift", tmp_path / "new.swift"]
    for source, version in zip(sources, ["old", "new"], strict=True):
        source.write_text(f"#!/bin/sh\necho {version}\n")
    real_run = subprocess.run
    compile_fixture(monkeypatch, [])
    if hard_link_errno is not None:
        def unavailable(*args):
            raise OSError(hard_link_errno, "hard links unavailable")
        monkeypatch.setattr(os, "link", unavailable)
    installed = Barrier(2)

    def compile_and_execute(source):
        executable = ensure_swift_helper(source, binary)
        installed.wait(timeout=5)
        result = real_run([str(executable)], capture_output=True, text=True, check=True, timeout=5)
        return executable, result.stdout.strip()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compile_and_execute, sources))
    assert [result[1] for result in results] == ["old", "new"]
    assert results[0][0] != results[1][0]
    for source, (executable, _) in zip(sources, results, strict=True):
        assert ensure_swift_helper(source, binary) == executable
        assert swift_helper_path(source, binary) == executable
    if app_bundle:
        assert results[0][0].parent.parent != results[1][0].parent.parent
    assert not list(tmp_path.rglob(".*.swift"))


def test_compiler_uses_hashed_snapshot_when_source_changes_and_changes_back(monkeypatch, tmp_path):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("old")

    def compile(command, **kwargs):
        assert Path(command[-3]) != source
        source.write_text("new")
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        source.write_text("old")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", compile)
    assert ensure_swift_helper(source, binary).read_text() == "old"


@pytest.mark.parametrize("link_error", sorted({errno.ENOTSUP, errno.EOPNOTSUPP}))
def test_no_link_or_exclusive_rename_has_actionable_error_and_cleans_temps(monkeypatch, tmp_path, link_error):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("new")
    binary.write_text("legacy executable")
    compile_fixture(monkeypatch, [])

    def no_links(*args):
        raise OSError(link_error, "hard links unavailable")

    def no_rename(*args):
        raise OSError(errno.ENOTSUP, "exclusive rename unavailable")

    monkeypatch.setattr(os, "link", no_links)
    monkeypatch.setattr("apple_mcp_common.native.rename_without_replacement", no_rename)
    with pytest.raises(NativeHelperError) as error:
        ensure_swift_helper(source, binary)
    assert error.value.error_code == "HELPER_CACHE_INSTALL_FAILED"
    assert "helper build directory" in error.value.suggestion
    assert binary.read_text() == "legacy executable"
    assert not swift_helper_path(source, binary).exists()
    assert not list(tmp_path.rglob(".*"))


def test_same_source_fallback_publish_never_replaces_the_winner(monkeypatch, tmp_path):
    source, binary = tmp_path / "source.swift", tmp_path / "helper"
    source.write_text("same source")
    barrier = Barrier(4)

    def compile(command, **kwargs):
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        barrier.wait(timeout=5)
        return subprocess.CompletedProcess(command, 0, "", "")

    def no_links(*args):
        raise OSError(errno.ENOTSUP, "hard links unavailable")

    monkeypatch.setattr(subprocess, "run", compile)
    monkeypatch.setattr(os, "link", no_links)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: ensure_swift_helper(source, binary), range(4)))
    assert len(set(paths)) == 1
    assert paths[0].read_text() == "same source"
    assert not list(tmp_path.rglob(".*"))
