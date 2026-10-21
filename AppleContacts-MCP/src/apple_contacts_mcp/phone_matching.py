"""Phone and email matching for Contacts lookups.

Import these helpers instead of copying them, so every server resolves a
phone number or email address to the same contact.

Rules:

- Emails match exactly, ignoring case and surrounding whitespace.
- Phones compare digits and extension. Formatting, ``tel:`` and spaces are ignored.
- A number under ``MIN_PHONE_DIGITS`` digits (a short code such as ``12345``)
  only matches the same digits exactly.
- Two international numbers (written with ``+`` or ``00``) must be the same digits.
- Two national numbers must be the same digits after dropping one leading
  trunk ``0``. ``555-1234`` does not match ``(212) 555-1234``, because a national
  number has no country code to leave out.
- An international number matches a national one when it has the same digits
  (only the ``+`` was left off), or when the national number, without its trunk
  ``0``, is a 7+ digit suffix and the digits in front of it are exactly a
  country calling code, optionally followed by a trunk ``0``
  (``+44 (0)20 7946 0958`` matches ``020 7946 0958``). A different area code
  never passes as a country code. An area code equal to a country code still
  matches; telling those apart needs each country's numbering plan.
"""

from __future__ import annotations

import re

# ITU-T E.164 country calling codes (1 to 3 digits).
COUNTRY_CALLING_CODES: frozenset[str] = frozenset({
    "1", "7", "20", "27", "30", "31", "32", "33", "34", "36", "39", "40", "41", "43", "44", "45",
    "46", "47", "48", "49", "51", "52", "53", "54", "55", "56", "57", "58", "60", "61", "62", "63",
    "64", "65", "66", "81", "82", "84", "86", "90", "91", "92", "93", "94", "95", "98", "211",
    "212", "213", "216", "218", "220", "221", "222", "223", "224", "225", "226", "227", "228",
    "229", "230", "231", "232", "233", "234", "235", "236", "237", "238", "239", "240", "241",
    "242", "243", "244", "245", "246", "247", "248", "249", "250", "251", "252", "253", "254",
    "255", "256", "257", "258", "260", "261", "262", "263", "264", "265", "266", "267", "268",
    "269", "290", "291", "297", "298", "299", "350", "351", "352", "353", "354", "355", "356",
    "357", "358", "359", "370", "371", "372", "373", "374", "375", "376", "377", "378", "379",
    "380", "381", "382", "383", "385", "386", "387", "389", "420", "421", "423", "500", "501",
    "502", "503", "504", "505", "506", "507", "508", "509", "590", "591", "592", "593", "594",
    "595", "596", "597", "598", "599", "670", "672", "673", "674", "675", "676", "677", "678",
    "679", "680", "681", "682", "683", "685", "686", "687", "688", "689", "690", "691", "692",
    "800", "808", "850", "852", "853", "855", "856", "870", "878", "880", "881", "882", "883",
    "886", "888", "960", "961", "962", "963", "964", "965", "966", "967", "968", "970", "971",
    "972", "973", "974", "975", "976", "977", "979", "991", "992", "993", "994", "995", "996",
    "998",
})
MIN_PHONE_DIGITS = 7
# The name PR #62 used for the same limit.
MIN_PHONE_HANDLE_DIGITS = MIN_PHONE_DIGITS

_PHONE_PATTERN = re.compile(
    r"(?:tel:)?(?=[+\d()./-]*\d)(?P<base>[+\d()./-]+)"
    r"(?:(?:ext(?:ension|n)?\.?[:=]?|x[:=]?|#|;ext=)(?P<extension>\d+))?"
)
_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def phone_parts(value: str) -> tuple[str, str | None] | None:
    """The digits and extension of a phone number, or None when the value is not one."""
    compact = re.sub(r"\s+", "", value.strip().lower())
    match = _PHONE_PATTERN.fullmatch(compact)
    if match is None:
        return None
    return re.sub(r"\D+", "", match.group("base")), match.group("extension")


def normalize_phone(value: str) -> str | None:
    """``digits`` or ``digits;ext=N`` for a phone number, or None when the value is not one."""
    parts = phone_parts(value)
    if parts is None:
        return None
    digits, extension = parts
    return digits if extension is None else f"{digits};ext={extension}"


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_email(value: str) -> bool:
    return _EMAIL_PATTERN.fullmatch(value.strip()) is not None


def has_international_prefix(value: str) -> bool:
    """Whether the number is written with ``+`` or the ``00`` international prefix."""
    compact = re.sub(r"[\s()./-]+", "", value.strip().lower()).removeprefix("tel:")
    return compact.startswith(("+", "00"))


def drop_trunk_zero(digits: str) -> str:
    """Drop the 00 international prefix, or else a single leading 0 (the national trunk prefix)."""
    return digits[2:] if digits.startswith("00") else digits.removeprefix("0")


def same_email(a: str, b: str) -> bool:
    return bool(normalize_email(a)) and normalize_email(a) == normalize_email(b)


def same_phone(a: str, b: str) -> bool:
    """Whether two phone values are the same number and extension under the module rules."""
    a_parts, b_parts = phone_parts(a), phone_parts(b)
    if a_parts is None or b_parts is None or a_parts[1] != b_parts[1]:
        return False
    a_digits, b_digits = a_parts[0], b_parts[0]
    if len(a_digits) < MIN_PHONE_DIGITS or len(b_digits) < MIN_PHONE_DIGITS:
        return a_digits == b_digits
    a_international, b_international = has_international_prefix(a), has_international_prefix(b)
    a_number, b_number = drop_trunk_zero(a_digits), drop_trunk_zero(b_digits)
    if a_international == b_international:
        return a_number == b_number
    international, national, national_digits = (a_number, b_number, b_digits) if a_international else (b_number, a_number, a_digits)
    if international == national_digits:
        return True
    if len(national) < MIN_PHONE_DIGITS or not international.endswith(national):
        return False
    prefix = international[: len(international) - len(national)]
    return prefix in COUNTRY_CALLING_CODES or (prefix.endswith("0") and prefix[:-1] in COUNTRY_CALLING_CODES)
