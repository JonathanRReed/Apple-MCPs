import asyncio
import io
import os
from pathlib import Path

import pytest

from apple_files_mcp.files_bridge import FilesBridge, FilesBridgeError


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_move_refuses_existing_destination(tmp_path, kind):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_text("source")
    if kind == "file":
        destination.write_text("keep")
    elif kind == "directory":
        destination.mkdir()
    else:
        destination.symlink_to(tmp_path / "missing")
    with pytest.raises(FilesBridgeError) as error:
        FilesBridge((tmp_path,)).move_path(str(source), str(destination))
    assert error.value.error_code == "PATH_ALREADY_EXISTS"
    assert source.read_text() == "source"
    if kind == "file":
        assert destination.read_text() == "keep"
    elif kind == "directory":
        assert destination.is_dir()
    else:
        assert destination.is_symlink()


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_exclusive_move_succeeds_for_new_destination(tmp_path, kind):
    source, destination = tmp_path / "source", tmp_path / "new"
    if kind == "file":
        source.write_text("source")
    elif kind == "directory":
        source.mkdir()
        (source / "child").write_text("keep")
    else:
        source.symlink_to(tmp_path / "missing")
    FilesBridge((tmp_path,)).move_path(str(source), str(destination))
    assert not source.exists() and not source.is_symlink()
    if kind == "file":
        assert destination.read_text() == "source"
    elif kind == "directory":
        assert (destination / "child").read_text() == "keep"
    else:
        assert destination.is_symlink()


@pytest.mark.parametrize("operation", ["delete", "move"])
@pytest.mark.parametrize("outside", [False, True])
def test_mutations_operate_on_link_instead_of_target(tmp_path, operation, outside):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = (tmp_path if outside else allowed) / "target"
    target.write_text("keep")
    link = allowed / "link"
    link.symlink_to(target)
    bridge = FilesBridge((allowed,))
    if operation == "delete":
        bridge.delete_path(str(link))
    else:
        moved = allowed / "moved"
        bridge.move_path(str(link), str(moved))
        assert moved.is_symlink() and moved.readlink() == target
    assert not link.is_symlink()
    assert target.read_text() == "keep"


def test_parent_link_cannot_escape_scope(tmp_path):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    target = outside / "target"
    target.write_text("keep")
    (allowed / "directory-link").symlink_to(outside, target_is_directory=True)
    bridge = FilesBridge((allowed,))
    with pytest.raises(FilesBridgeError) as error:
        bridge.delete_path(str(allowed / "directory-link" / "target"))
    assert error.value.error_code == "PATH_NOT_ALLOWED"
    with pytest.raises(FilesBridgeError):
        bridge.delete_path(str(allowed / ".."))
    assert target.read_text() == "keep"


def test_external_link_read_is_blocked(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("keep")
    link = allowed / "link"
    link.symlink_to(outside)
    with pytest.raises(FilesBridgeError) as error:
        FilesBridge((allowed,)).read_text_file(str(link))
    assert error.value.error_code == "PATH_NOT_ALLOWED"


@pytest.mark.parametrize("limit", [-1, 0, True, 10485761])
def test_text_read_rejects_invalid_limit(tmp_path, limit):
    target = tmp_path / "file"
    target.write_text("text")
    with pytest.raises(FilesBridgeError) as error:
        FilesBridge((tmp_path,)).read_text_file(str(target), limit)
    assert error.value.error_code == "INVALID_INPUT"


def test_text_read_is_bounded_before_decoding(monkeypatch, tmp_path):
    target = tmp_path / "file"
    target.write_text("placeholder")
    reads = []

    class Stream(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    monkeypatch.setattr(Path, "open", lambda *a, **kw: Stream(b"abcdef"))
    assert FilesBridge((tmp_path,)).read_text_file(str(target), 3) == ("abc", True)
    assert reads == [4]


def test_fifo_read_is_rejected_without_opening(tmp_path):
    target = tmp_path / "fifo"
    os.mkfifo(target)
    with pytest.raises(FilesBridgeError) as error:
        FilesBridge((tmp_path,)).read_text_file(str(target))
    assert error.value.error_code == "NOT_A_FILE"


def test_concurrent_moves_cannot_replace_each_others_destination(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    sources = [tmp_path / "a", tmp_path / "b"]
    for source in sources:
        source.write_text(source.name)
    destination = tmp_path / "destination"
    bridge = FilesBridge((tmp_path,))
    def move(source):
        try:
            bridge.move_path(str(source), str(destination))
            return "moved"
        except FilesBridgeError as error:
            return error.error_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(move, sources))
    assert sorted(outcomes) == ["PATH_ALREADY_EXISTS", "moved"]
    assert sum(source.exists() for source in sources) == 1
    assert destination.read_text() in {"a", "b"}


@pytest.mark.parametrize("where", ["source_leaf", "source_parent", "destination_leaf", "destination_parent"])
def test_public_move_rejects_nul_before_path_or_native_calls(monkeypatch, tmp_path, where):
    from apple_files_mcp import tools
    source, destination = tmp_path / "source", tmp_path / "new"
    source.write_text("owned fixture")
    source_text, destination_text = str(source), str(destination)
    if where == "source_leaf":
        source_text += "\0suffix"
    elif where == "source_parent":
        source_text = str(tmp_path) + "\0suffix/source"
    elif where == "destination_leaf":
        destination_text += "\0suffix"
    else:
        destination_text = str(tmp_path) + "\0suffix/new"
    bridge = FilesBridge((tmp_path,))
    monkeypatch.setenv("APPLE_FILES_MCP_SAFETY_MODE", "safe_manage")
    tools.load_settings.cache_clear()
    monkeypatch.setattr(tools, "_bridge", lambda: bridge)

    def forbidden(*args, **kwargs):
        raise AssertionError("malformed input reached filesystem/native work")

    monkeypatch.setattr("apple_files_mcp.files_bridge.Path", forbidden)
    monkeypatch.setattr(bridge, "_rename_without_replace", forbidden)
    try:
        result = asyncio.run(tools.files_move_path(source_text, destination_text, None))
        assert result.ok is False and result.error.error_code == "INVALID_INPUT"
    finally:
        tools.load_settings.cache_clear()
    assert source.read_text() == "owned fixture"
    assert not destination.exists()
