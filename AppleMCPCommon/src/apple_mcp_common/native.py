"""Content-aware, atomic compilation for cached Swift command-line helpers."""

import errno
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from apple_mcp_common.atomic import rename_without_replacement

_CACHE_SUGGESTION = "Choose a local helper build directory that supports hard links or atomic exclusive renames, then retry."


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
