import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='AppleScriptObjC requires macOS')


@pytest.mark.parametrize('script', ['get_note', 'list_notes'])
@pytest.mark.parametrize('timezone', ['UTC', 'Europe/Berlin', 'America/New_York'])
def test_notes_epoch_is_absolute_across_timezones_and_dst(script, timezone, tmp_path):
    source = (Path(__file__).parents[1] / f'src/apple_notes_mcp/applescripts/{script}.applescript').read_text()
    handler = 'on date_to_epoch(' + source.split('on date_to_epoch(', 1)[1].split('end date_to_epoch', 1)[0] + 'end date_to_epoch'
    probe = tmp_path / 'epoch.applescript'
    probe.write_text('''use framework "Foundation"
use scripting additions
on run argv
    current application's NSTimeZone's setDefaultTimeZone:(current application's NSTimeZone's timeZoneWithName:(item 1 of argv))
    set inputDate to (current application's NSDate's dateWithTimeIntervalSince1970:1710055800) as date
    return my date_to_epoch(inputDate)
end run
''' + handler)
    result = subprocess.run([shutil.which('osascript'), str(probe), timezone], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert int(float(result.stdout.strip())) == 1710055800
