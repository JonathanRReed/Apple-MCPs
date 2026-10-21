"""Content-aware, atomic compilation for cached Swift command-line helpers."""

import errno
import hashlib
import os
import plistlib
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from apple_mcp_common.atomic import rename_without_replacement

_CACHE_SUGGESTION = "Choose a local helper build directory that supports hard links or atomic exclusive renames, then retry."
_SIGN_SUGGESTION = "Make sure the Xcode Command Line Tools are installed (run `xcode-select --install`), then retry. Nothing was installed, so the next call rebuilds and signs the helper again."


class NativeHelperError(Exception):
    def __init__(self, error_code: str, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.suggestion = suggestion


def swift_helper_path(source: Path, binary: Path) -> Path:
    """Locate a source version without changing another version's executable."""
    return _versioned_path(binary, hashlib.sha256(source.read_bytes()).hexdigest())


def _versioned_path(binary: Path, digest: str) -> Path:
    if binary.parent.name == "MacOS" and binary.parent.parent.name == "Contents":
        bundle = binary.parent.parent.parent
        if bundle.suffix == ".app":
            return bundle.with_name(f"{bundle.stem}-{digest}.app") / "Contents" / "MacOS" / binary.name
    return binary.with_name(f"{binary.name}-{digest}")


def ensure_swift_helper(source: Path, binary: Path) -> Path:
    """Return an immutable executable path that the caller must execute.

    Different installed package versions may compile concurrently into the same
    cache. Each source digest gets its own executable (and application bundle),
    so another version cannot replace it after this function returns.
    """
    source_bytes = source.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    binary = _versioned_path(binary, digest)
    if binary.is_file():
        return binary
    try:
        binary.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix="." + binary.name + ".", dir=binary.parent)
    except OSError as error:
        raise NativeHelperError("HELPER_CACHE_UNAVAILABLE", f"Could not prepare helper cache at '{binary.parent}': {error}.", _CACHE_SUGGESTION) from error
    os.close(descriptor)
    temporary = Path(temporary_name)
    source_temporary = temporary.with_name(temporary.name + ".swift")
    try:
        # Compile the bytes we hashed, even if the package is upgraded in place.
        source_temporary.write_bytes(source_bytes)
        try:
            result = subprocess.run(
                ["swiftc", "-parse-as-library", "-O", str(source_temporary), "-o", str(temporary)],
                capture_output=True, text=True, check=False, timeout=300,
            )
        except subprocess.TimeoutExpired as error:
            raise NativeHelperError("HELPER_COMPILE_TIMEOUT", "Swift helper compilation timed out.") from error
        except OSError as error:
            raise NativeHelperError("SWIFTC_UNAVAILABLE", f"Could not run swiftc: {error}.") from error
        if result.returncode != 0:
            raise NativeHelperError("HELPER_COMPILE_FAILED", result.stderr.strip() or result.stdout.strip() or "Swift helper compilation failed.")
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise NativeHelperError("HELPER_SOURCE_CHANGED", "Swift helper source changed during compilation; retry.")
        temporary.chmod(0o755)
        try:
            # A hard link publishes a complete file atomically and never replaces
            # a competing compiler's complete result for this same source.
            try:
                os.link(temporary, binary)
            except OSError as error:
                if error.errno not in {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP}:
                    raise
                # Some supported custom cache filesystems cannot make hard links.
                # Use the same complete-file, exclusive rename as file moves.
                rename_without_replacement(temporary, binary)
        except FileExistsError:
            if not binary.is_file():
                raise NativeHelperError("HELPER_CACHE_INSTALL_FAILED", "The helper cache destination is not a regular executable.", _CACHE_SUGGESTION) from None
        except OSError as error:
            raise NativeHelperError("HELPER_CACHE_INSTALL_FAILED", f"Could not atomically install helper at '{binary}': {error}.", _CACHE_SUGGESTION) from error
        return binary
    finally:
        temporary.unlink(missing_ok=True)
        source_temporary.unlink(missing_ok=True)


CODESIGN = "/usr/bin/codesign"
# Bump when the bundle layout, Info.plist recipe or signing changes, so every
# helper is rebuilt into a new versioned directory instead of reusing a stale one.
_BUNDLE_RECIPE = b"apple-mcps-helper-bundle-v1\0"


@dataclass(frozen=True)
class HelperBundle:
    """How a Swift helper is packaged as a macOS application bundle.

    macOS privacy (TCC) identifies a requesting app by its bundle identifier and
    code signature, and only prompts when the app's Info.plist explains the
    access. ``swiftc`` alone produces a linker-signed Mach-O whose signing
    identifier is the temporary output name and whose signature does not bind
    any Info.plist, so each build looked like a different, unexplained program.
    """

    executable: str
    display_name: str
    bundle_identifier: str
    usage_descriptions: Mapping[str, str] = field(default_factory=dict)

    def info_plist(self) -> dict[str, object]:
        return {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": self.display_name,
            "CFBundleExecutable": self.executable,
            "CFBundleIdentifier": self.bundle_identifier,
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": self.display_name,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0",
            "CFBundleVersion": "1",
            # A bare CLI has no bundle identity, so EventKit used to route resyncs
            # through Calendar.app and bring it to the front. These keys keep the
            # helper out of the Dock and away from keyboard focus.
            "LSBackgroundOnly": True,
            "LSUIElement": True,
            **dict(self.usage_descriptions),
        }


def _bundle_digest(source_bytes: bytes, spec: HelperBundle) -> str:
    plist = plistlib.dumps(spec.info_plist(), sort_keys=True)
    return hashlib.sha256(_BUNDLE_RECIPE + plist + b"\0" + source_bytes).hexdigest()


def _bundle_executable(root: Path, spec: HelperBundle) -> Path:
    return root / f"{spec.display_name}.app" / "Contents" / "MacOS" / spec.executable


def helper_bundle_executable(source: Path, build_dir: Path, spec: HelperBundle) -> Path:
    """Locate the executable for this source and bundle recipe, built or not."""
    return _bundle_executable(build_dir / f"{spec.executable}-{_bundle_digest(source.read_bytes(), spec)}", spec)


def sign_helper_bundle(bundle: Path, spec: HelperBundle) -> bool:
    """Ad-hoc sign ``bundle`` with a stable identifier and its Info.plist bound.

    Returns False only when codesign does not exist (not macOS); the helper then
    keeps its linker signature. When codesign runs but fails or times out this
    raises HELPER_SIGN_FAILED, so a bundle without its stable identity is never
    published to the cache, where it would be reused forever.
    """
    try:
        result = subprocess.run(
            [CODESIGN, "--force", "--sign", "-", "--identifier", spec.bundle_identifier, str(bundle)],
            capture_output=True, text=True, check=False, timeout=60,
        )
    except FileNotFoundError:
        return False
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NativeHelperError("HELPER_SIGN_FAILED", f"Could not sign '{bundle.name}': {error}.", _SIGN_SUGGESTION) from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
        raise NativeHelperError("HELPER_SIGN_FAILED", f"codesign could not sign '{bundle.name}': {detail}", _SIGN_SUGGESTION)
    return True


def ensure_helper_bundle(source: Path, build_dir: Path, spec: HelperBundle) -> Path:
    """Compile ``source`` into a signed app bundle and return its executable.

    Each source and recipe version gets its own directory
    (``<executable>-<digest>/<display name>.app``), assembled and signed in a
    temporary directory and published with one exclusive rename, so another
    package version can never replace a bundle after this returns. The bundle
    file name stays readable because macOS shows it in privacy prompts and in
    System Settings.
    """
    source_bytes = source.read_bytes()
    digest = _bundle_digest(source_bytes, spec)
    version_dir = build_dir / f"{spec.executable}-{digest}"
    executable = _bundle_executable(version_dir, spec)
    if executable.is_file():
        return executable
    try:
        build_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{spec.executable}-build-", dir=build_dir))
    except OSError as error:
        raise NativeHelperError("HELPER_CACHE_UNAVAILABLE", f"Could not prepare helper cache at '{build_dir}': {error}.", _CACHE_SUGGESTION) from error
    try:
        source_snapshot = staging / "helper.swift"
        staged_version = staging / version_dir.name
        staged_executable = _bundle_executable(staged_version, spec)
        try:
            # Compile the bytes we hashed, even if the package is upgraded in place.
            source_snapshot.write_bytes(source_bytes)
            staged_executable.parent.mkdir(parents=True)
            with (staged_executable.parent.parent / "Info.plist").open("wb") as stream:
                plistlib.dump(spec.info_plist(), stream, sort_keys=True)
        except OSError as error:
            raise NativeHelperError("HELPER_CACHE_UNAVAILABLE", f"Could not prepare helper cache at '{build_dir}': {error}.", _CACHE_SUGGESTION) from error
        try:
            result = subprocess.run(
                ["swiftc", "-parse-as-library", "-O", str(source_snapshot), "-o", str(staged_executable)],
                capture_output=True, text=True, check=False, timeout=300,
            )
        except subprocess.TimeoutExpired as error:
            raise NativeHelperError("HELPER_COMPILE_TIMEOUT", "Swift helper compilation timed out.") from error
        except OSError as error:
            raise NativeHelperError("SWIFTC_UNAVAILABLE", f"Could not run swiftc: {error}.") from error
        if result.returncode != 0:
            raise NativeHelperError("HELPER_COMPILE_FAILED", result.stderr.strip() or result.stdout.strip() or "Swift helper compilation failed.")
        if source.read_bytes() != source_bytes:
            raise NativeHelperError("HELPER_SOURCE_CHANGED", "Swift helper source changed during compilation; retry.")
        staged_executable.chmod(0o755)
        sign_helper_bundle(staged_executable.parent.parent.parent, spec)
        try:
            rename_without_replacement(staged_version, version_dir)
        except FileExistsError:
            pass
        except OSError as error:
            if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise NativeHelperError("HELPER_CACHE_INSTALL_FAILED", f"Could not atomically install helper at '{version_dir}': {error}.", _CACHE_SUGGESTION) from error
        if not executable.is_file():
            # A concurrent build of the same source won the rename, but left no executable.
            raise NativeHelperError("HELPER_CACHE_INSTALL_FAILED", "The helper cache destination is not a complete application bundle.", _CACHE_SUGGESTION)
        return executable
    finally:
        shutil.rmtree(staging, ignore_errors=True)
