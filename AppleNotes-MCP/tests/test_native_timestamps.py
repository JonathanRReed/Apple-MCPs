import json
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


@pytest.mark.parametrize('script', ['get_note', 'list_notes'])
@pytest.mark.parametrize('locale', ['en_US', 'de_DE'])
@pytest.mark.parametrize('epoch', [0, -1, -2208988800, 536870911, 536870912, 1710055800, 1760500000, 1760500123, 4102444800, 32503680000])
def test_notes_epoch_is_valid_json_across_locales_and_integer_boundaries(script, locale, epoch, tmp_path):
    source = (Path(__file__).parents[1] / f'src/apple_notes_mcp/applescripts/{script}.applescript').read_text()
    handler = 'on date_to_epoch(' + source.split('on date_to_epoch(', 1)[1].split('end date_to_epoch', 1)[0] + 'end date_to_epoch'
    probe = tmp_path / 'epoch-json.applescript'
    probe.write_text(f'''use framework "Foundation"
use scripting additions
on run argv
    set inputDate to (current application's NSDate's dateWithTimeIntervalSince1970:{epoch}) as date
    set epochText to my date_to_epoch(inputDate)
    set localeName to current application's NSLocale's currentLocale()'s localeIdentifier() as text
    return "{{" & quote & "locale" & quote & ":" & quote & localeName & quote & "," & quote & "created_epoch" & quote & ":" & epochText & "," & quote & "modified_epoch" & quote & ":" & epochText & "}}"
end run
''' + handler)
    result = subprocess.run([shutil.which('osascript'), str(probe), '-AppleLocale', locale], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['locale'] == locale
    for field in ('created_epoch', 'modified_epoch'):
        assert type(data[field]) in (int, float)
        assert data[field] == epoch
