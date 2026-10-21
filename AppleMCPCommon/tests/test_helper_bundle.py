import plistlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from apple_mcp_common import native
from apple_mcp_common.native import CODESIGN, HelperBundle, NativeHelperError, ensure_helper_bundle, helper_bundle_executable
from apple_mcp_common.privacy import helper_permission_guide

SPEC = HelperBundle(
    executable="example-bridge",
    display_name="Example MCP Helper",
    bundle_identifier="io.github.jonathanrreed.apple-mcps.example-bridge",
    usage_descriptions={"NSContactsUsageDescription": "Reads contacts."},
)


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "helper.swift"
    path.write_text("first")
    return path


def build_fixture(monkeypatch, calls, *, sign_result=0):
    def run(command, **kwargs):
        calls.append(command)
        if command[0] == CODESIGN:
            assert kwargs["timeout"] == 60
            return subprocess.CompletedProcess(command, sign_result, "", "" if sign_result == 0 else "codesign failed")
        assert kwargs["timeout"] == 300
        Path(command[-1]).write_bytes(Path(command[-3]).read_bytes())
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)


def test_builds_signed_bundle_with_bound_identity(monkeypatch, tmp_path, source):
    calls = []
    build_fixture(monkeypatch, calls)
    build = tmp_path / "build"

    executable = ensure_helper_bundle(source, build, SPEC)

    app = executable.parent.parent.parent
    assert app.name == "Example MCP Helper.app"
    assert app.parent.parent == build
    assert app.parent.name.startswith("example-bridge-")
    assert executable.read_text() == "first"
    assert executable.stat().st_mode & 0o111
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == SPEC.bundle_identifier
    assert info["CFBundleExecutable"] == "example-bridge"
    assert info["CFBundleDisplayName"] == info["CFBundleName"] == "Example MCP Helper"
    assert info["CFBundlePackageType"] == "APPL"
    assert info["LSUIElement"] is True
    assert info["NSContactsUsageDescription"] == "Reads contacts."
    swiftc, codesign = calls
    assert swiftc[:3] == ["swiftc", "-parse-as-library", "-O"]
    # Signed with a stable identifier after Info.plist exists, so the signature binds it.
    assert codesign[:-1] == [CODESIGN, "--force", "--sign", "-", "--identifier", SPEC.bundle_identifier]
    assert codesign[-1].endswith(f"/{app.parent.name}/Example MCP Helper.app")
    assert sorted(path.name for path in build.iterdir()) == [app.parent.name]
    assert helper_bundle_executable(source, build, SPEC) == executable


def test_complete_bundle_is_reused_without_rebuilding(monkeypatch, tmp_path, source):
    calls = []
    build_fixture(monkeypatch, calls)
    first = ensure_helper_bundle(source, tmp_path, SPEC)
    calls.clear()

    assert ensure_helper_bundle(source, tmp_path, SPEC) == first
    assert calls == []


def test_source_or_recipe_change_builds_new_version_and_keeps_old(monkeypatch, tmp_path, source):
    calls = []
    build_fixture(monkeypatch, calls)
    first = ensure_helper_bundle(source, tmp_path, SPEC)
    reworded = HelperBundle(SPEC.executable, SPEC.display_name, SPEC.bundle_identifier, {"NSContactsUsageDescription": "Reads contacts for you."})

    second = ensure_helper_bundle(source, tmp_path, reworded)
    source.write_text("second")
    third = ensure_helper_bundle(source, tmp_path, SPEC)

    assert len({first, second, third}) == 3
    assert first.read_text() == "first"
    assert third.read_text() == "second"


def test_missing_codesign_is_not_fatal(monkeypatch, tmp_path, source):
    # Without codesign (not macOS) the helper keeps its linker signature.
    calls = []
    build_fixture(monkeypatch, calls)
    real_run = subprocess.run

    def no_codesign(command, **kwargs):
        if command[0] == CODESIGN:
            raise FileNotFoundError(CODESIGN)
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", no_codesign)

    executable = ensure_helper_bundle(source, tmp_path, SPEC)

    assert executable.is_file()


@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_signing_failure_publishes_nothing_and_retries(monkeypatch, tmp_path, source, failure):
    # Review follow-up: a failed signature used to be published and then reused
    # forever, leaving the helper without its stable identity.
    calls = []
    build_fixture(monkeypatch, calls, sign_result=1)
    if failure == "timeout":
        real_run = subprocess.run

        def slow_codesign(command, **kwargs):
            if command[0] == CODESIGN:
                raise subprocess.TimeoutExpired(command, 60)
            return real_run(command, **kwargs)

        monkeypatch.setattr(subprocess, "run", slow_codesign)

    with pytest.raises(NativeHelperError) as raised:
        ensure_helper_bundle(source, tmp_path, SPEC)

    assert raised.value.error_code == "HELPER_SIGN_FAILED"
    assert "xcode-select" in (raised.value.suggestion or "")
    assert not helper_bundle_executable(source, tmp_path, SPEC).exists()
    assert not any(path.name.startswith(".") for path in tmp_path.iterdir())

    build_fixture(monkeypatch, calls)
    assert ensure_helper_bundle(source, tmp_path, SPEC).is_file()


@pytest.mark.parametrize(
    ("failure", "code"),
    [("exit", "HELPER_COMPILE_FAILED"), ("timeout", "HELPER_COMPILE_TIMEOUT"), ("missing", "SWIFTC_UNAVAILABLE"), ("source_changed", "HELPER_SOURCE_CHANGED")],
)
def test_failed_build_publishes_nothing(monkeypatch, tmp_path, source, failure, code):
    def run(command, **kwargs):
        if failure == "missing":
            raise FileNotFoundError("swiftc")
        Path(command[-1]).write_text("partial")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 300)
        if failure == "source_changed":
            source.write_text("changed")
        return subprocess.CompletedProcess(command, 1 if failure == "exit" else 0, "", "failed")

    monkeypatch.setattr(subprocess, "run", run)
    build = tmp_path / "build"

    with pytest.raises(NativeHelperError) as error:
        ensure_helper_bundle(source, build, SPEC)

    assert error.value.error_code == code
    assert list(build.iterdir()) == []


def test_unwritable_cache_has_actionable_error(tmp_path, source):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")

    with pytest.raises(NativeHelperError) as error:
        ensure_helper_bundle(source, blocker / "build", SPEC)

    assert error.value.error_code == "HELPER_CACHE_UNAVAILABLE"
    assert "helper build directory" in error.value.suggestion


def test_concurrent_builds_of_same_source_share_one_winner(monkeypatch, tmp_path, source):
    barrier = Barrier(3)

    def run(command, **kwargs):
        if command[0] != CODESIGN:
            Path(command[-1]).write_text(Path(command[-1]).parent.parent.parent.parent.parent.name)
            barrier.wait(timeout=5)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    build = tmp_path / "build"
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(lambda _: ensure_helper_bundle(source, build, SPEC), range(3)))

    assert len(set(paths)) == 1
    assert paths[0].read_text().startswith(".example-bridge-build-")
    assert [path.name for path in build.iterdir()] == [paths[0].parent.parent.parent.parent.name]


def test_unsupported_exclusive_rename_has_actionable_error(monkeypatch, tmp_path, source):
    import errno

    build_fixture(monkeypatch, [])

    def unsupported(*args):
        raise OSError(errno.ENOTSUP, "filesystem operation unavailable")

    monkeypatch.setattr(native, "rename_without_replacement", unsupported)
    with pytest.raises(NativeHelperError) as error:
        ensure_helper_bundle(source, tmp_path / "build", SPEC)

    assert error.value.error_code == "HELPER_CACHE_INSTALL_FAILED"
    assert list((tmp_path / "build").iterdir()) == []


def test_permission_guide_explains_host_and_helper_identity():
    guide = helper_permission_guide("contacts", "Contacts", "AddressBook", SPEC)

    text = " ".join(guide["steps"] + guide["notes"])
    assert guide["domain"] == "contacts"
    assert guide["helper_bundle_identifier"] == SPEC.bundle_identifier
    assert "System Settings > Privacy & Security > Contacts" in text
    assert "'Example MCP Helper'" in text
    assert f"tccutil reset AddressBook {SPEC.bundle_identifier}" in text
    assert "app that started this MCP server" in text
