from apple_shortcuts_mcp.shortcuts_bridge import ShortcutsBridge, ShortcutsBridgeError


class Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_parse_shortcuts_and_folders(monkeypatch) -> None:
    bridge = ShortcutsBridge(shortcuts_command="shortcuts", timeout_seconds=5)

    def fake_run_cli(args):
        key = tuple(args)
        if key == ("list", "--show-identifiers"):
            return Completed(
                0,
                "Open Trunk (9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D)\nStart Car (29B15189-C4FC-4823-89AE-45617D461CBA)\n",
            )
        if key == ("list", "--folders"):
            return Completed(0, "Home\nCar\n")
        if key == ("list", "--show-identifiers", "--folder-name", "Home"):
            return Completed(0, "Open Trunk (9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D)\n")
        if key == ("list", "--show-identifiers", "--folder-name", "Car"):
            return Completed(0, "Start Car (29B15189-C4FC-4823-89AE-45617D461CBA)\n")
        raise AssertionError(f"Unexpected args: {args}")

    monkeypatch.setattr(bridge, "_run_cli", fake_run_cli)

    shortcuts = bridge.list_shortcuts()
    folders = bridge.list_folders()

    assert shortcuts[0].name == "Open Trunk"
    assert shortcuts[0].identifier == "9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D"
    assert folders[0].folder_name == "Home"
    assert folders[0].shortcut_count == 1


def test_run_shortcut_maps_failure(monkeypatch) -> None:
    bridge = ShortcutsBridge(shortcuts_command="shortcuts", timeout_seconds=5)

    monkeypatch.setattr(
        bridge,
        "resolve_shortcut",
        lambda value: __import__("apple_shortcuts_mcp.models", fromlist=["ShortcutInfo"]).ShortcutInfo(
            name=value, identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D"
        ),
    )
    monkeypatch.setattr(bridge, "_run_cli", lambda args, input_data=None: Completed(1, "", "Error: The input of the shortcut could not be processed."))

    try:
        bridge.run_shortcut("Open Trunk", input_paths=["/etc/hosts"])
    except ShortcutsBridgeError as exc:
        assert exc.error_code == "SHORTCUT_INPUT_FAILED"
    else:
        raise AssertionError("Expected ShortcutsBridgeError")


def test_run_shortcut_passes_input_text(monkeypatch) -> None:
    bridge = ShortcutsBridge(shortcuts_command="shortcuts", timeout_seconds=5)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        bridge,
        "resolve_shortcut",
        lambda value: __import__("apple_shortcuts_mcp.models", fromlist=["ShortcutInfo"]).ShortcutInfo(
            name=value, identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D"
        ),
    )

    def fake_run_cli(args, input_data=None):
        captured["args"] = args
        captured["input_data"] = input_data
        return Completed(0, "done", "")

    monkeypatch.setattr(bridge, "_run_cli", fake_run_cli)

    result = bridge.run_shortcut("Open Trunk", input_text="hello from stdin")

    assert result.exit_code == 0
    assert captured["args"] == ["run", "9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D"]
    assert captured["input_data"] == "hello from stdin"


def _bridge_with_root(monkeypatch, root, captured):
    bridge = ShortcutsBridge(shortcuts_command="shortcuts", timeout_seconds=5, allowed_roots=(root,))
    monkeypatch.setattr(
        bridge,
        "resolve_shortcut",
        lambda value: __import__("apple_shortcuts_mcp.models", fromlist=["ShortcutInfo"]).ShortcutInfo(
            name=value, identifier="9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D"
        ),
    )

    def fake_run_cli(args, input_data=None):
        captured.append(args)
        return Completed(0, "", "")

    monkeypatch.setattr(bridge, "_run_cli", fake_run_cli)
    return bridge


def test_run_shortcut_writes_output_inside_allowed_folder(monkeypatch, tmp_path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    captured: list[list[str]] = []
    bridge = _bridge_with_root(monkeypatch, root, captured)

    result = bridge.run_shortcut("Open Trunk", output_path=str(root / "sub" / ".." / "out.txt"))

    expected = str(root.resolve() / "out.txt")
    assert captured == [["run", "9A2D4AFE-D4B5-418E-814A-DB97BAB3BE4D", "--output-path", expected]]
    assert result.artifacts[0].path == expected


def test_run_shortcut_refuses_output_outside_allowed_folders(monkeypatch, tmp_path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    captured: list[list[str]] = []
    bridge = _bridge_with_root(monkeypatch, root, captured)

    for path in (
        str(outside / "out.txt"),
        str(root / ".." / "outside" / "out.txt"),
        str(root / "link" / "out.txt"),
        str(root),
        str(root) + "/",
        str(tmp_path / "allowed-extra" / "out.txt"),
    ):
        try:
            bridge.run_shortcut("Open Trunk", output_path=path)
        except ShortcutsBridgeError as exc:
            assert exc.error_code == "PATH_NOT_ALLOWED", path
        else:
            raise AssertionError(f"Expected PATH_NOT_ALLOWED for {path}")
    assert captured == []
