import pytest

from apple_calendar_mcp.alarm_validation import validate_alarms


@pytest.mark.parametrize('value', ['2026-03-08T01:30:00', '2026-03-08T03:30:00', '2026-11-01T01:30:00'])
def test_absolute_alarm_requires_offset_across_dst(value):
    with pytest.raises(ValueError, match='explicit UTC'):
        validate_alarms([{'absolute_iso':value}])


@pytest.mark.parametrize('value', ['2026-03-08T01:30:00-05:00', '2026-03-08T03:30:00-04:00', '2026-11-01T01:30:00-04:00', '2026-11-01T01:30:00-05:00'])
def test_absolute_alarm_preserves_explicit_offset_across_dst(value):
    assert validate_alarms([{'absolute_iso':value}]) == [{'absolute_iso':value}]
