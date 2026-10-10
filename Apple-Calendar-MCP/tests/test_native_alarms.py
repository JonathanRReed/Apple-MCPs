"""Native alarm parsing tests use EventKit types without touching a live calendar."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="EventKit requires macOS")


@pytest.fixture(scope="module")
def native_alarm_probe(tmp_path_factory):
    compiler = shutil.which("swiftc")
    if compiler is None:
        pytest.skip("Swift compiler is required")
    directory = tmp_path_factory.mktemp("native-alarm-probe")
    source = Path(__file__).parents[1] / "src/apple_calendar_mcp/apple_pim_bridge.swift"
    bridge = source.read_text().replace("@main\nstruct ApplePIMBridge", "struct ApplePIMBridge", 1)
    harness = r'''
@main
struct AlarmProbe {
    static func main() {
        do {
            let command = CommandLine.arguments[1]
            if command == "offset" {
                let seconds = Double(CommandLine.arguments[2])!
                let value = ApplePIMBridge.safeAlarmOffsetMinutes(seconds)
                if let offset = value { print(offset) } else { print("null") }
            } else {
                let data = CommandLine.arguments[2].data(using: .utf8)!
                let raw = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
                let alarms = try ApplePIMBridge.eventAlarms(raw)
                print("ok:\(alarms.count)")
            }
        } catch let failure as BridgeFailure {
            print(failure.errorCode)
        } catch {
            print("UNEXPECTED_ERROR")
        }
    }
}
'''
    probe_source = directory / "probe.swift"
    probe_source.write_text(bridge + harness)
    executable = directory / "probe"
    completed = subprocess.run(
        [compiler, "-parse-as-library", str(probe_source), "-o", str(executable)],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return executable


def _probe(executable, command, value):
    completed = subprocess.run(
        [str(executable), command, value], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


@pytest.mark.parametrize("alarms", [
    [{"minutes_before": True}], [{"minutes_before": False}],
    [{"minutes_before": -1}], [{"minutes_before": 525601}],
    [{"minutes_before": 1e30}], [{"minutes_before": 0.5}],
    [{"minutes_before": "inf"}], [{"minutes_before": "nan"}],
    [{"minutes_before": "1e400"}], [{"minutes_before": []}],
    [{"minutes_before": 15, "absolute_iso": "2026-03-27T09:00:00Z"}],
    [{}], [{"unknown": 15}], [{"absolute_iso": None}], [{"absolute_iso": True}],
    [{"absolute_iso": "invalid"}], None, {}, ["15"],
    [{"minutes_before": 15}] * 101,
])
def test_native_alarm_validation_rejects_invalid_payload(native_alarm_probe, alarms):
    assert _probe(native_alarm_probe, "alarms", json.dumps(alarms)) == "INVALID_INPUT"


@pytest.mark.parametrize("alarms,count", [
    ([], 0), ([{"minutes_before": 0}], 1), ([{"minutes_before": 525600}], 1),
    ([{"minutes_before": "525600"}], 1),
    ([{"absolute_iso": "2026-03-27T09:00:00Z"}], 1),
    ([{"minutes_before": 15}] * 100, 100),
])
def test_native_alarm_validation_accepts_boundaries(native_alarm_probe, alarms, count):
    assert _probe(native_alarm_probe, "alarms", json.dumps(alarms)) == f"ok:{count}"


@pytest.mark.parametrize("seconds,expected", [
    ("-900", "-15"), ("90", "1"), ("-90", "-1"),
    ("inf", "null"), ("-inf", "null"), ("nan", "null"),
    ("1e30", "null"), ("-1e30", "null"),
])
def test_native_external_alarm_offset_never_traps(native_alarm_probe, seconds, expected):
    assert _probe(native_alarm_probe, "offset", seconds) == expected
