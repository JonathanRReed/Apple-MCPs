import pytest

from apple_contacts_mcp.phone_matching import (
    COUNTRY_CALLING_CODES,
    drop_trunk_zero,
    has_international_prefix,
    is_email,
    normalize_email,
    normalize_phone,
    phone_parts,
    same_email,
    same_phone,
)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("+1 (555) 123-4567", "5551234567"),
        ("+1 555 123 4567", "1 555 123 4567"),
        ("(555) 123-4567", "001 555 123 4567"),
        ("+44 (0)20 7946 0958", "020 7946 0958"),
        ("+44 20 7946 0958", "0044 20 7946 0958"),
        ("020 7946 0958", "20 7946 0958"),
        ("tel:+34612345678", "612 345 678"),
        ("555-1234 x5", "+1 555-1234 ext. 5"),
        ("12345", "12-345"),
    ],
)
def test_same_phone_matches(a, b) -> None:
    assert same_phone(a, b)
    assert same_phone(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("555-1234", "(212) 555-1234"),
        ("555-1234", "(310) 555-1234"),
        ("+1 (555) 123-4567", "9991234567"),
        ("+999 612 345 678", "612345678"),
        ("+212 555 1234", "0212 555 1234"),
        ("555-1234 x5", "555-1234 x50"),
        ("12345", "012345"),
        ("1234", "+1 555 123 1234"),
        ("", ""),
        ("Ann", "Ann"),
    ],
)
def test_same_phone_rejects(a, b) -> None:
    assert not same_phone(a, b)
    assert not same_phone(b, a)


def test_helpers() -> None:
    assert {"1", "44", "212", "998"} <= COUNTRY_CALLING_CODES
    assert phone_parts("tel:555-1234;ext=5") == ("5551234", "5")
    assert phone_parts("Ann") is None
    assert normalize_phone("+1 (555) 123-4567 x9") == "15551234567;ext=9"
    assert normalize_email("  ANN@Work.com ") == "ann@work.com"
    assert is_email("ann@work.com") and not is_email("ann at work")
    assert same_email("ANN@work.com", "ann@work.com") and not same_email("", "")
    assert has_international_prefix("+44 20") and has_international_prefix("(00) 44") and not has_international_prefix("020")
    assert drop_trunk_zero("0044") == "44" and drop_trunk_zero("020") == "20"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("1 (555) 123-4567", "5551234567", True),
        ("1-555-123-4567", "(555) 123-4567", True),
        ("1 555 123 4567", "+1 555 123 4567", True),
        ("13812345678", "3812345678", False),
        ("138 1234 5678", "3812345678", False),
        ("1 (212) 555-1234", "555-1234", False),
        ("1 (155) 123-4567", "1551234567", False),
    ],
)
def test_separated_north_american_country_code(a, b, expected):
    # A US number saved with its country code but no "+" still matches the
    # 10-digit form; unseparated 11-digit numbers (Chinese mobiles) do not.
    assert same_phone(a, b) is expected
    assert same_phone(b, a) is expected
