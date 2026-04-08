from pathlib import Path
import subprocess

from apple_files_mcp.files_bridge import FilesBridge


def test_recent_files_skips_timed_out_roots(monkeypatch, tmp_path) -> None:
    docs_root = tmp_path / "Documents"
    docs_root.mkdir()
    file_path = docs_root / "a.txt"
    file_path.write_text("hello")

    bridge = FilesBridge((Path("/Users/test/Downloads"), docs_root))

    def fake_run(command, capture_output, text, check, timeout):
        assert command[0] == "find"
        root = command[1]
        if root == "/Users/test/Downloads":
            raise subprocess.TimeoutExpired(command, timeout)

        class Completed:
            stdout = f"1712530000\t{file_path}\n"
            stderr = ""

        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    entries = bridge.recent_files(limit=5)

    assert len(entries) == 1
    assert entries[0].path == str(file_path)
