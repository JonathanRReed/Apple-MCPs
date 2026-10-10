"""Content-aware, atomic compilation for cached Swift command-line helpers."""

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path


class NativeHelperError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def ensure_swift_helper(source: Path, binary: Path) -> bool:
    """Return whether a new executable was installed; never trust file mtimes."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stamp = binary.with_name(binary.name + ".source.sha256")
    if binary.is_file() and stamp.is_file() and stamp.read_text().strip() == digest:
        return False
    binary.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="." + binary.name + ".", dir=binary.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    stamp_temporary = temporary.with_name(temporary.name + ".sha256")
    try:
        try:
            result = subprocess.run(
                ["swiftc", "-parse-as-library", "-O", str(source), "-o", str(temporary)],
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
        stamp_temporary.write_text(digest + "\n")
        temporary.replace(binary)
        stamp_temporary.replace(stamp)
        return True
    finally:
        temporary.unlink(missing_ok=True)
        stamp_temporary.unlink(missing_ok=True)
