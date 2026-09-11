"""ISBN normalization, validation and 10<->13 conversion (SPEC.md section 7)."""

from __future__ import annotations


class InvalidISBNError(ValueError):
    """Raised when an ISBN fails length/checksum validation."""


def normalize(raw: str) -> str:
    """Strip hyphens/whitespace and upper-case the check char (X)."""
    return "".join(raw.split()).replace("-", "").replace("–", "").upper()


def _isbn10_check_digit(body9: str) -> str:
    total = sum((10 - i) * int(ch) for i, ch in enumerate(body9))
    remainder = (11 - (total % 11)) % 11
    return "X" if remainder == 10 else str(remainder)


def _isbn13_check_digit(body12: str) -> str:
    total = sum((1 if i % 2 == 0 else 3) * int(ch) for i, ch in enumerate(body12))
    return str((10 - (total % 10)) % 10)


def is_valid_isbn10(value: str) -> bool:
    if len(value) != 10:
        return False
    if not value[:9].isdigit():
        return False
    if not (value[9].isdigit() or value[9] == "X"):
        return False
    return _isbn10_check_digit(value[:9]) == value[9]


def is_valid_isbn13(value: str) -> bool:
    if len(value) != 13 or not value.isdigit():
        return False
    if not (value.startswith("978") or value.startswith("979")):
        return False
    return _isbn13_check_digit(value[:12]) == value[12]


def to_isbn13(isbn10: str) -> str:
    body = "978" + isbn10[:9]
    return body + _isbn13_check_digit(body)


def to_isbn10(isbn13: str) -> str | None:
    """Convert an ISBN-13 to ISBN-10. Only the 978 prefix has an ISBN-10 equivalent."""
    if not isbn13.startswith("978"):
        return None
    body = isbn13[3:12]
    return body + _isbn10_check_digit(body)


class ISBN:
    """A validated ISBN exposing both the 13- and 10-digit forms."""

    __slots__ = ("isbn13", "isbn10")

    def __init__(self, isbn13: str, isbn10: str | None) -> None:
        self.isbn13 = isbn13
        self.isbn10 = isbn10

    @classmethod
    def parse(cls, raw: str) -> ISBN:
        value = normalize(raw)
        if len(value) == 13:
            if not is_valid_isbn13(value):
                raise InvalidISBNError("invalid ISBN-13 checksum or prefix")
            return cls(value, to_isbn10(value))
        if len(value) == 10:
            if not is_valid_isbn10(value):
                raise InvalidISBNError("invalid ISBN-10 checksum")
            return cls(to_isbn13(value), value)
        raise InvalidISBNError("ISBN must be 10 or 13 characters after normalization")
